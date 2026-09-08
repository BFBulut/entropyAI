"""Comprehensive automated tests for slash commands, skills discovery, MCP discovery, and popup UI."""

import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from entropy.core.slash_commands import (
    BUILTIN_AGY_COMMANDS,
    SlashCommand,
    SlashCommandRegistry,
    get_dynamic_skill_commands,
    get_dynamic_mcp_commands,
    get_dynamic_tool_commands,
)
from entropy.mcp.manager import MCPManager
from entropy.tools.synthesizer import default_synthesizer
from entropy.ui.widgets.slash_command_popup import SlashCommandPopupWidget
from entropy.ui.modes.chat_mode import ChatInputField, ChatModeWindow
from entropy.ui.modes.zen_mode import ZenModeWindow
from entropy.core.agy_bridge import AgyProcessBridge

def test_builtin_commands_defined():
    """Verify essential Antigravity slash commands are registered with descriptions."""
    cmd_names = [c.name for c in BUILTIN_AGY_COMMANDS]
    required_cmds = [
        "/boost",
        "/goal",
        "/grill-me",
        "/teamwork-preview",
        "/team-upgrade",
        "/learn",
        "/plan",
        "/browser",
        "/schedule",
        "/clear",
        "/help"
    ]
    for req in required_cmds:
        assert req in cmd_names, f"Expected {req} to be in BUILTIN_AGY_COMMANDS"

    for cmd in BUILTIN_AGY_COMMANDS:
        assert cmd.name.startswith("/")
        assert len(cmd.description) > 5
        assert cmd.category == "builtin"
        assert cmd.badge == "⚡ AGY"

def test_dynamic_skill_discovery(tmp_path):
    """Verify dynamic discovery of skills without restart or update."""
    skills_root = tmp_path / "skills"
    skills_root.mkdir()

    # Create a dynamic skill folder on the fly
    new_skill_dir = skills_root / "quantum-optimizer"
    new_skill_dir.mkdir()
    skill_md = new_skill_dir / "SKILL.md"
    skill_md.write_text("""---
name: quantum-optimizer
description: Kuantum algoritmaları ve optimizasyon mimarı.
---
# Quantum Optimizer Body
""", encoding="utf-8")

    # Fetch dynamic skills pointing to this directory
    skills = get_dynamic_skill_commands(project_dir=tmp_path)
    skill_names = [s.name for s in skills]
    assert "/quantum-optimizer" in skill_names

    opt_cmd = next(s for s in skills if s.name == "/quantum-optimizer")
    assert "Kuantum algoritmaları" in opt_cmd.description
    assert opt_cmd.category == "skill"
    assert opt_cmd.badge == "🎯 YETENEK"

def test_dynamic_mcp_discovery():
    """Verify MCPManager returns server commands and tool commands."""
    mgr = MCPManager()
    mcp_cmds = get_dynamic_mcp_commands(mcp_manager=mgr)
    cmd_names = [c.name for c in mcp_cmds]

    # Verify standard servers exist
    assert "/obsidian" in cmd_names
    assert "/supabase" in cmd_names
    assert "/chrome-devtools-mcp" in cmd_names
    assert "/gmp-code-assist" in cmd_names

    # Verify sub-tools exist
    assert "/obsidian:search_notes" in cmd_names
    assert "/supabase:execute_sql" in cmd_names
    assert "/chrome-devtools-mcp:navigate" in cmd_names

    # Dynamically register a new tool and verify it appears immediately
    mgr.register_tool("obsidian", "graph_export", "Obsidian bilgi grafını dışa aktarır")
    updated_cmds = get_dynamic_mcp_commands(mcp_manager=mgr)
    updated_names = [c.name for c in updated_cmds]
    assert "/obsidian:graph_export" in updated_names

def test_dynamic_tool_synthesizer_commands():
    """Verify self-synthesized tools show up in commands."""
    code = "def custom_calc(a: int, b: int) -> int:\n    return a + b\n"
    default_synthesizer.register_python_tool("custom_calc", "Özel matematiksel hesaplama aracı", code)

    tool_cmds = get_dynamic_tool_commands()
    tool_names = [c.name for c in tool_cmds]
    assert "/custom_calc" in tool_names

    calc_cmd = next(c for c in tool_cmds if c.name == "/custom_calc")
    assert "Özel matematiksel hesaplama" in calc_cmd.description
    assert calc_cmd.category == "tool"
    assert calc_cmd.badge == "🛠️ ARAÇ"

def test_slash_command_filtering():
    """Test prefix and substring ranking of commands."""
    reg = SlashCommandRegistry()
    
    # Query "/" returns all
    all_cmds = reg.filter_commands("/")
    assert len(all_cmds) >= len(BUILTIN_AGY_COMMANDS)

    # Prefix query "/boo" matches "/boost" first
    boost_matches = reg.filter_commands("/boo")
    assert len(boost_matches) >= 1
    assert boost_matches[0].name == "/boost"

    # Prefix query "/gri" matches "/grill-me"
    grill_matches = reg.filter_commands("/gri")
    assert len(grill_matches) >= 1
    assert grill_matches[0].name == "/grill-me"

    # Prefix query "/team" matches team commands
    team_matches = reg.filter_commands("/team")
    names = [c.name for c in team_matches]
    assert "/teamwork-preview" in names
    assert "/team-upgrade" in names

def test_slash_popup_widget(qapp):
    """Test SlashCommandPopupWidget UI creation and navigation."""
    popup = SlashCommandPopupWidget()
    sample_cmds = [
        SlashCommand("/boost", "Derin akıl yürütme", "builtin", "⚡ AGY", "#00F0FF"),
        SlashCommand("/goal", "Hedef belirleme", "builtin", "⚡ AGY", "#00F0FF"),
        SlashCommand("/learn", "Öğrenme modu", "builtin", "⚡ AGY", "#00FF9D"),
    ]
    popup.set_commands(sample_cmds)
    assert popup.list_widget.count() == 3
    assert popup.list_widget.currentRow() == 0

    popup.select_next()
    assert popup.list_widget.currentRow() == 1

    popup.select_previous()
    assert popup.list_widget.currentRow() == 0

    selected_collector = []
    popup.command_selected.connect(lambda cmd: selected_collector.append(cmd))
    popup.confirm_selection()
    assert selected_collector == ["/boost"]
    assert not popup.isVisible()

def test_chat_input_field_autocomplete(qapp):
    """Test ChatInputField reacts to / and auto-completes selection."""
    dummy_parent = QWidget()
    dummy_parent.bridge = AgyProcessBridge()
    input_field = ChatInputField(parent_chat=dummy_parent)

    # Initially popup hidden
    assert not input_field.popup.isVisible()

    # User types "/"
    input_field.setText("/")
    assert input_field.popup.isVisible()
    assert input_field.popup.list_widget.count() > 0

    # User types "/boo"
    input_field.setText("/boo")
    assert input_field.popup.isVisible()
    assert input_field.popup.list_widget.count() >= 1

    # Simulate hitting Enter key on the field to accept autocomplete
    enter_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    input_field.keyPressEvent(enter_event)

    # Verify command was completed with trailing space and popup is hidden
    assert input_field.text() == "/boost "
    assert not input_field.popup.isVisible()

    # Typing arguments after space keeps popup hidden
    input_field.setText("/boost kodları incele")
    assert not input_field.popup.isVisible()

    # Escape key hides popup
    input_field.setText("/lea")
    assert input_field.popup.isVisible()
    esc_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    input_field.keyPressEvent(esc_event)
    assert not input_field.popup.isVisible()

    input_field.close()

def test_zen_mode_core_label_and_slash(qapp, monkeypatch):
    """Test central AI core label says 'Entropy AI' and slash commands function."""
    bridge = AgyProcessBridge()
    zen = ZenModeWindow(bridge=bridge)

    # Verify central AI core label
    assert zen.core_status_lbl.text() == "Entropy AI"
    assert "Entropi" not in zen.core_status_lbl.text()

    # Verify status updates
    zen._update_status("thinking")
    assert zen.core_status_lbl.text() == "Entropy AI (Düşünüyor...)"
    assert "Entropi" not in zen.core_status_lbl.text()

    zen._update_status("executing")
    assert zen.core_status_lbl.text() == "Entropy AI (Yürütülüyor...)"

    zen._update_status("error")
    assert zen.core_status_lbl.text() == "Entropy AI (Hata)"

    zen._update_status("idle")
    assert zen.core_status_lbl.text() == "Entropy AI"

    # Test /clear command
    zen.chat_browser.setText("Old message")
    zen.chat_input.setText("/clear")
    zen._on_send_chat()
    assert "Sohbet ve terminal ekranı sıfırlandı." in zen.chat_browser.toPlainText()

    # Test /help command
    zen.chat_input.setText("/help")
    zen._on_send_chat()
    assert "KULLANILABİLİR KOMUTLAR" in zen.chat_browser.toPlainText()

    zen.close()

def test_chat_mode_slash_commands(qapp):
    """Test ChatModeWindow slash commands."""
    bridge = AgyProcessBridge()
    sent_args = []
    def mock_send_prompt_async(prompt, image_attachments=None, pdf_attachments=None, active_skill=None, mode="accept-edits", **kwargs):
        sent_args.append({"prompt": prompt, "active_skill": active_skill, "mode": mode})
    bridge.send_prompt_async = mock_send_prompt_async
    chat = ChatModeWindow(bridge=bridge)

    # Test /clear command
    chat.chat_browser.setText("Some chat text")
    chat.input_field.setText("/clear")
    chat._on_send()
    assert "Sohbet ekranı sıfırlandı." in chat.chat_browser.toPlainText()

    # Test /help command
    chat.input_field.setText("/help")
    chat._on_send()
    assert "KULLANILABİLİR KOMUTLAR" in chat.chat_browser.toPlainText()

    # Test slash skill sets active skill and badge in chat
    chat.input_field.setText("/financial-auditor bilançoyu oku")
    chat._on_send()
    assert "YETENEK: /financial-auditor" in chat.chat_browser.toPlainText()

    chat.close()

def test_mcp_cross_instance_caching_and_tools():
    """Verify MCPManager caches servers and shares custom tools across separate instances."""
    mgr1 = MCPManager()
    servers1 = mgr1.list_servers()
    assert len(servers1) >= 4

    # New instance must benefit from shared cache
    mgr2 = MCPManager()
    assert MCPManager._cached_servers is not None

    # Register custom tool on mgr1, verify mgr2 discovers it immediately without restart
    mgr1.register_tool("obsidian", "graph_neural_export", "Bilgi grafı dışa aktarımı")
    tools2 = mgr2.list_tools("obsidian")
    assert any(t["name"] == "graph_neural_export" for t in tools2)

def test_zen_mode_skill_handoff_and_badges(qapp):
    """Verify ZenModeWindow recognizes slash skills, updates telemetry, and passes active_skill."""
    bridge = AgyProcessBridge()
    sent_args = []
    def mock_send_prompt_async(prompt, image_attachments=None, pdf_attachments=None, active_skill=None, mode="accept-edits", **kwargs):
        sent_args.append({"prompt": prompt, "active_skill": active_skill, "mode": mode})

    bridge.send_prompt_async = mock_send_prompt_async
    zen = ZenModeWindow(bridge=bridge)

    # Invoke /plan
    zen.chat_input.setText("/plan REST API mimarisi")
    zen._on_send_chat()
    assert sent_args[-1]["mode"] == "plan"
    assert "AGY: /plan" in zen.chat_browser.toPlainText()

    # Invoke slash skill
    zen.chat_input.setText("/financial-auditor Q3 gelir tablosu")
    zen._on_send_chat()
    assert sent_args[-1]["active_skill"] == "financial-auditor"
    assert "YETENEK: /financial-auditor" in zen.chat_browser.toPlainText()

    zen.close()

def test_command_deduplication():
    """Verify SlashCommandRegistry deduplicates identical command names."""
    reg = SlashCommandRegistry()
    cmds = reg.get_all_commands()
    names = [c.name.lower() for c in cmds]
    assert len(names) == len(set(names)), "Command names must be strictly unique"

def test_popup_monitor_bounds_clamping(qapp):
    """Verify popup geometry clamps properly with screen bounds."""
    popup = SlashCommandPopupWidget()
    sample_cmds = [SlashCommand("/test", "Açıklama", "builtin", "⚡ AGY", "#00F0FF")]
    popup.set_commands(sample_cmds)

    dummy_input = QWidget()
    dummy_input.resize(400, 32)
    dummy_input.show()

    popup.show_at_input(dummy_input)
    assert popup.width() >= 400
    assert popup.height() >= 90
    popup.close()
    dummy_input.close()

