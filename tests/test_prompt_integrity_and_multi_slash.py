"""Comprehensive test suite for:
1. Skill detection engine improvements (set deduplication, \\b boundary checks, BM25 length penalty, autonomous-agent triggers).
2. Progressive disclosure & immutable prompt in AGY bridge (no 38KB markdown injection, clean chat turn save, Windows 32KB protection).
3. Multi-selection slash command popup UI & ChatInputField interaction.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from entropy.skills.manager import SkillManager, SkillDefinition
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.slash_commands import SlashCommand, SlashCommandRegistry
from entropy.ui.widgets.slash_command_popup import SlashCommandPopupWidget
from entropy.ui.modes.chat_mode import ChatInputField, ChatModeWindow
from entropy.ui.modes.zen_mode import ZenModeWindow


# ---------------------------------------------------------------------------
# 1. SKILL DETECTION ENGINE TESTS
# ---------------------------------------------------------------------------

def test_skill_detection_token_set_deduplication(tmp_path):
    """Verify that duplicate words in prompt do NOT unfairly inflate the score."""
    mgr = SkillManager(root_skills_dir=tmp_path)
    mgr.state_file = tmp_path / "skills_state.json"

    # Skill with 'proje' in description
    mgr.create_skill(
        name="project-tracker",
        description="proje durum takibi ve proje yonetimi",
        instructions="# Project Tracker"
    )

    # 1. Repeated casual word 'proje' must NOT falsely inflate score to trigger the skill
    prompt_repeated = "yeni bir alt proje proje proje proje proje proje"
    detected_repeated = mgr.auto_detect_skill_for_prompt(prompt_repeated)
    assert detected_repeated is None, "Repeated single token must not inflate score to trigger skill"

    # 2. Genuine multi-word query SHOULD trigger the skill
    prompt_genuine = "proje durum takibi yap"
    detected_genuine = mgr.auto_detect_skill_for_prompt(prompt_genuine)
    assert detected_genuine is not None
    assert detected_genuine.name == "project-tracker"


def test_skill_detection_word_boundary_prevents_false_positive(tmp_path):
    """Verify 3-letter tag like 'erc' does NOT trigger on 'gerçekleştirecek'."""
    mgr = SkillManager(root_skills_dir=tmp_path)
    mgr.state_file = tmp_path / "skills_state.json"

    # Skill with 3-letter tag 'erc' (e.g. ERC-20 token auditor)
    s_dir = tmp_path / "erc-auditor"
    s_dir.mkdir()
    (s_dir / "SKILL.md").write_text("""---
name: erc-auditor
description: Ethereum token standard checking
tags: erc, token
---
# ERC Auditor
""", encoding="utf-8")

    # Prompt contains 'gerçekleştirecek', which has 'erc' as a substring inside the word
    prompt = "Yarın sabah yeni bir test gerçekleştirecek misiniz?"
    detected = mgr.auto_detect_skill_for_prompt(prompt)
    assert detected is None, "Tag 'erc' should NOT match inside 'gerçekleştirecek'"

    # Prompt with standalone 'erc' SHOULD match
    prompt_valid = "Bu kontrat bir erc standardına uygun mu?"
    detected_valid = mgr.auto_detect_skill_for_prompt(prompt_valid)
    assert detected_valid is not None
    assert detected_valid.name == "erc-auditor"


def test_skill_detection_bm25_length_penalty(tmp_path):
    """Verify BM25 description length penalty prevents bloated descriptions from beating concise skills."""
    mgr = SkillManager(root_skills_dir=tmp_path)
    mgr.state_file = tmp_path / "skills_state.json"

    # Skill A: concise description
    mgr.create_skill(
        name="crypto-trader",
        description="Kripto para arbitraj ve likidite havuzu optimizasyonu",
        instructions="# Crypto"
    )

    # Skill B: bloated description packed with filler words and a faint match
    bloated_desc = "Kripto " + ("dolgu kelimesi " * 500)
    mgr.create_skill(
        name="bloated-skill",
        description=bloated_desc,
        instructions="# Bloated"
    )

    detected = mgr.auto_detect_skill_for_prompt("Kripto para arbitrajını başlat")
    assert detected is not None
    assert detected.name == "crypto-trader", "Concise matching skill must win over bloated description"


def test_skill_detection_autonomous_agent_priority_boost(tmp_path):
    """Verify autonomous-agent triggers (ajan, orkestratör, agent desk, ofis, space, pixel agent)."""
    mgr = SkillManager(root_skills_dir=tmp_path)
    mgr.state_file = tmp_path / "skills_state.json"

    mgr.create_skill(
        name="autonomous-agent",
        description="Otonom ajan orkestrasyonu ve denetim ağaçları",
        instructions="# Autonomous Agent"
    )

    triggers = [
        "Sanal ofis alanındaki ajanları koordine et",
        "Agent desk üzerinde yeni bir alt görev başlat",
        "Orkestratör ile birlikte çalışan ajan mimarisi",
        "Pixel agent alanında simülasyon çalıştır",
        "Space içerisinde çalışan otonom ajanları listele",
    ]

    for prompt in triggers:
        detected = mgr.auto_detect_skill_for_prompt(prompt)
        assert detected is not None, f"Expected autonomous-agent for prompt: {prompt}"
        assert detected.name == "autonomous-agent", f"Expected autonomous-agent, got: {detected.name}"

    # Verify that Turkish 'ajans' (agency) does NOT falsely trigger 'ajan' (autonomous-agent)
    prompt_ajans = "Yeni bir ajans kuruyoruz, şirket vizyonu hazırla"
    assert mgr.auto_detect_skill_for_prompt(prompt_ajans) is None, "'ajans' must not falsely match 'ajan'"


# ---------------------------------------------------------------------------
# 2. AGY BRIDGE: PROGRESSIVE DISCLOSURE & IMMUTABLE PROMPT TESTS
# ---------------------------------------------------------------------------

def test_progressive_disclosure_and_immutable_user_prompt(tmp_path, monkeypatch):
    """Verify SKILL.md body (even 38KB) is NOT injected in prompt; raw user prompt is immutable."""
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    # Create a skill with huge 40KB instructions
    huge_instructions = "# Massive Skill\n" + ("Gereksinim satırı ve kural detayı...\n" * 1200)
    assert len(huge_instructions) > 35000

    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    s_dir = skills_dir / "big-auditor"
    s_dir.mkdir()
    (s_dir / "SKILL.md").write_text(f"""---
name: big-auditor
description: Kapsamlı denetim uzmanlığı
---
{huge_instructions}
""", encoding="utf-8")

    captured_cmds = []
    saved_turns = []

    def mock_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = [
            '{"event": "result", "result": {"response": "Tamamlandı"}}\n',
            ''
        ]
        mock_proc.wait.return_value = 0
        return mock_proc

    monkeypatch.setattr("subprocess.Popen", mock_popen)
    monkeypatch.setattr(bridge, "_save_chat_turn", lambda u, a: saved_turns.append((u, a)))

    original_user_prompt = "/boost /big-auditor bilançoyu analiz et"
    bridge._execute_prompt_worker(
        prompt=original_user_prompt,
        image_attachments=None,
        pdf_attachments=None,
        active_skill=None,
        mode="accept-edits"
    )

    assert len(captured_cmds) == 1
    cli_cmd = captured_cmds[0]

    # 1. Check that the 38KB body was NOT injected into CLI arguments
    full_cli_str = " ".join(cli_cmd)
    assert "Gereksinim satırı ve kural detayı..." not in full_cli_str
    assert len(full_cli_str) < 30000, f"CLI command payload exceeded safe limit: {len(full_cli_str)}"

    # 2. Verify progressive disclosure banner (compact 1-2 lines)
    assert "[AKTİF UZMANLIK YETENEĞİ: BIG-AUDITOR]" in full_cli_str
    assert "Kapsamlı denetim uzmanlığı" in full_cli_str
    assert "SKILL.md" in full_cli_str

    # 3. Verify user message is preserved intact in CLI payload
    assert original_user_prompt in full_cli_str

    # 4. Verify saved chat turn has raw, untainted user prompt
    assert len(saved_turns) == 1
    assert saved_turns[0][0] == original_user_prompt

    # 5. Verify /boost triggered --effort high
    assert "--effort" in cli_cmd
    effort_idx = cli_cmd.index("--effort")
    assert cli_cmd[effort_idx + 1] == "high"


def test_regex_boost_detection_anywhere_in_prompt(tmp_path, monkeypatch):
    """Verify /boost is detected anywhere in prompt via regex, adding --effort high."""
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    captured_cmds = []
    def mock_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = ['{"event": "result", "result": {"response": "OK"}}\n', '']
        mock_proc.wait.return_value = 0
        return mock_proc

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    prompts_with_boost = [
        "/boost derinlemesine düşün",
        "/plan /boost mimariyi oluştur",
        "Lütfen bu problemi /boost ile çöz",
        "/goal REST /boost /learn sistem",
    ]

    for p in prompts_with_boost:
        captured_cmds.clear()
        bridge._execute_prompt_worker(prompt=p, mode="accept-edits")
        assert len(captured_cmds) == 1
        cmd = captured_cmds[0]
        assert "--effort" in cmd, f"Expected --effort high for prompt: {p}"
        assert cmd[cmd.index("--effort") + 1] == "high"


def test_windows_32kb_limit_never_truncates_user_prompt(tmp_path, monkeypatch):
    """Verify system directive is truncated under 32KB payload pressure, but user message remains intact."""
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    captured_cmds = []
    def mock_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = ['{"event": "result", "result": {"response": "OK"}}\n', '']
        mock_proc.wait.return_value = 0
        return mock_proc

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    # User message of 15,000 characters
    long_user_prompt = "Önemli kod tablosu: " + ("fonksiyon_verisi " * 900)
    assert len(long_user_prompt) > 14000

    bridge._execute_prompt_worker(prompt=long_user_prompt, mode="accept-edits")
    assert len(captured_cmds) == 1
    cli_cmd = captured_cmds[0]

    # Find the -p argument
    p_idx = cli_cmd.index("-p")
    payload = cli_cmd[p_idx + 1]

    # User prompt must be fully present in payload
    assert long_user_prompt in payload
    assert "...[kısaltıldı]" not in payload
    assert len(payload) <= 26500, "Payload must be strictly below safe Windows limit"


# ---------------------------------------------------------------------------
# 3. SLASH MULTI-SELECTION UI & POPUP TESTS
# ---------------------------------------------------------------------------

def test_slash_popup_multi_selection_clicking(qapp):
    """Verify clicking multiple commands in SlashCommandPopupWidget keeps popup open and toggles properly."""
    popup = SlashCommandPopupWidget()
    sample_cmds = [
        SlashCommand("/boost", "Derin akıl yürütme", "builtin", "⚡ AGY", "#00F0FF"),
        SlashCommand("/plan", "Planlama modu", "builtin", "⚡ AGY", "#00F0FF"),
        SlashCommand("/learn", "Hafızaya kaydet", "builtin", "⚡ AGY", "#00FF9D"),
    ]
    popup.set_commands(sample_cmds)
    popup.show()

    updated_history = []
    popup.commands_updated.connect(lambda cmds: updated_history.append(list(cmds)))

    # Click first item: /boost
    item0 = popup.list_widget.item(0)
    popup._on_item_clicked(item0)
    assert popup.selected_commands == ["/boost"]
    assert popup.isVisible(), "Popup MUST stay open after clicking a command for multi-selection"
    assert popup._item_widgets["/boost"].check_lbl.text() == "[✓]"

    # Click second item: /plan
    item1 = popup.list_widget.item(1)
    popup._on_item_clicked(item1)
    assert popup.selected_commands == ["/boost", "/plan"]
    assert popup.isVisible(), "Popup MUST stay open after clicking second command"
    assert popup._item_widgets["/plan"].check_lbl.text() == "[✓]"

    # Click /boost again: should deselect it
    popup._on_item_clicked(item0)
    assert popup.selected_commands == ["/plan"]
    assert popup._item_widgets["/boost"].check_lbl.text() == "[ ]"

    # Confirm selection
    popup.confirm_selection()
    assert not popup.isVisible()
    assert updated_history[-1] == ["/plan"]
    popup.close()


def test_chat_input_field_multi_slash_sequential_selection(qapp):
    """Verify ChatInputField reacts to multi-selection from popup without requiring re-typing '/'."""
    dummy_parent = QWidget()
    dummy_parent.bridge = AgyProcessBridge()
    input_field = ChatInputField(parent_chat=dummy_parent)
    input_field.show()

    # 1. User types "/" -> popup opens
    # Öneriler 150 ms gecikmeyle hesaplanır (tuş başına dizin taramasını önlemek
    # için); test gecikmeyi beklemek yerine zamanlayıcıyı elle tetikler.
    input_field.setText("/")
    assert input_field._suggest_timer.isActive(), "öneri zamanlayıcısı kurulmadı"
    input_field._update_suggestions()
    assert input_field.popup.isVisible()

    # 2. Simulate multi-selection signal from popup: ["/boost", "/plan", "/learn"]
    input_field.popup.commands_updated.emit(["/boost", "/plan", "/learn"])

    # Text in input field should be updated with trailing space
    assert input_field.text() == "/boost /plan /learn "

    # 3. User types message text after the selected commands
    input_field.setText("/boost /plan /learn mimariyi analiz et")
    # Typing normal text after commands hides the popup
    assert not input_field.popup.isVisible()

    input_field.close()
    dummy_parent.close()


def test_zen_and_chat_mode_multi_slash_execution(qapp, monkeypatch):
    """Verify ZenModeWindow and ChatModeWindow handle multi-slash commands in prompt."""
    # Pencereler gerçek SkillManager'ı kurar; kullanıcının uygulamada bir yeteneği
    # pasife alması (~/.entropy/skills_state.json) bu testi etkilememeli.
    monkeypatch.setattr(SkillManager, "_load_state", lambda self: {})
    bridge = AgyProcessBridge()
    sent_calls = []

    def mock_send(prompt, image_attachments=None, pdf_attachments=None, active_skill=None, mode="accept-edits", **kwargs):
        sent_calls.append({"prompt": prompt, "active_skill": active_skill, "mode": mode})

    bridge.send_prompt_async = mock_send

    # 1. Test Zen Mode with /boost /plan /financial-auditor
    zen = ZenModeWindow(bridge=bridge)
    zen.chat_input.setText("/boost /plan /financial-auditor 2026 Q3 bilançosunu incele")
    zen._on_send_chat()

    assert len(sent_calls) == 1
    call = sent_calls[-1]
    assert call["mode"] == "plan", "Presence of /plan must set mode to 'plan'"
    assert call["active_skill"] == "financial-auditor", "Slash skill must be detected"
    assert "⚡ AGY: /boost" in zen.chat_browser.toPlainText() or "AGY: /boost" in zen.chat_browser.toPlainText()
    assert "⚡ AGY: /plan" in zen.chat_browser.toPlainText() or "AGY: /plan" in zen.chat_browser.toPlainText()
    assert "🎯 YETENEK: /financial-auditor" in zen.chat_browser.toPlainText() or "YETENEK: /financial-auditor" in zen.chat_browser.toPlainText()
    zen.close()

    # 2. Test Chat Mode with /boost /plan /financial-auditor
    chat = ChatModeWindow(bridge=bridge)
    chat.input_field.setText("/boost /plan /financial-auditor 2026 Q3 bilançosunu incele")
    chat._on_send()

    assert len(sent_calls) == 2
    chat_call = sent_calls[-1]
    assert chat_call["mode"] == "plan"
    assert chat_call["active_skill"] == "financial-auditor"
    assert "AGY: /boost" in chat.chat_browser.toPlainText()
    assert "AGY: /plan" in chat.chat_browser.toPlainText()
    assert "YETENEK: /financial-auditor" in chat.chat_browser.toPlainText()
    chat.close()


def test_pdf_attachment_preserves_immutable_raw_user_prompt(tmp_path, monkeypatch):
    """Verify that attaching a PDF document does NOT mutate raw_user_prompt in saved chat turns or events."""
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    saved_turns = []
    captured_cmds = []

    def mock_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = ['{"event": "result", "result": {"response": "PDF analizi tamamlandı."}}\n', '']
        mock_proc.wait.return_value = 0
        return mock_proc

    monkeypatch.setattr("subprocess.Popen", mock_popen)
    monkeypatch.setattr(bridge, "_save_chat_turn", lambda u, a: saved_turns.append((u, a)))

    # Mock PDF ingestion engine to return sample pages
    mock_pdf_result = {
        "metadata": {"filename": "bilanco.pdf", "pages": 2, "word_count": 50},
        "full_content": "Şirket Net Karı: 50M TL. Dönen Varlıklar: 120M TL.",
        "pages": [{"page": 1, "text": "Sayfa 1"}, {"page": 2, "text": "Sayfa 2"}],
        "digest_path": str(tmp_path / "bilanco_digest.md")
    }

    with patch("entropy.skills.pdf_engine.PDFIngestionEngine") as MockEngine:
        instance = MockEngine.return_value
        instance.ingest_and_store_memory.return_value = mock_pdf_result

        user_query = "Lütfen bilançoyu özetle"
        fake_pdf = tmp_path / "bilanco.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 sample")

        bridge._execute_prompt_worker(
            prompt=user_query,
            image_attachments=None,
            pdf_attachments=[str(fake_pdf)],
            active_skill=None,
            mode="accept-edits"
        )

    assert len(saved_turns) == 1
    # Raw user prompt saved to history MUST be pure user query, NEVER polluted with PDF blocks
    assert saved_turns[0][0] == user_query, f"Expected clean user query, got: {saved_turns[0][0]}"

    # CLI command payload MUST contain both PDF ingestion content and the user query
    assert len(captured_cmds) == 1
    cli_str = " ".join(captured_cmds[0])
    assert user_query in cli_str
    assert "EKLENEN PDF BELGESİ: bilanco.pdf" in cli_str
    # Verify PDF content is not duplicated twice
    assert cli_str.count("EKLENEN PDF BELGESİ: bilanco.pdf") == 1


def test_multi_slash_directives_and_effort_parameter(tmp_path, monkeypatch):
    """Verify /grill-me, /teamwork-preview, /goal, and /effort parameters are parsed and injected."""
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    captured_cmds = []
    def mock_popen(cmd, **kwargs):
        captured_cmds.append(cmd)
        mock_proc = MagicMock()
        mock_proc.stdout.readline.side_effect = ['{"event": "result", "result": {"response": "OK"}}\n', '']
        mock_proc.wait.return_value = 0
        return mock_proc

    monkeypatch.setattr("subprocess.Popen", mock_popen)

    # 1. Test /grill-me and /effort medium
    bridge._execute_prompt_worker(
        prompt="/effort medium /grill-me Bu mimariyi değerlendir",
        mode="accept-edits"
    )
    cmd = captured_cmds[-1]
    assert "--effort" in cmd
    assert cmd[cmd.index("--effort") + 1] == "medium"
    cmd_str = " ".join(cmd)
    assert "[MOD: GRILL-ME]" in cmd_str

    # 2. Test /teamwork-preview and /goal
    captured_cmds.clear()
    bridge._execute_prompt_worker(
        prompt="/teamwork-preview /goal REST API yayınlamak Yeni mikroservis mimarisi",
        mode="accept-edits"
    )
    cmd = captured_cmds[-1]
    cmd_str = " ".join(cmd)
    assert "[MOD: TEAMWORK-PREVIEW]" in cmd_str
    assert "[OTURUM HEDEFİ]:" in cmd_str
    assert "REST API yayınlamak" in cmd_str


def test_slash_popup_explicit_clear_and_confirm(qapp):
    """Verify that clearing selection in popup and clicking confirm applies empty selection without resurrecting highlighted item."""
    popup = SlashCommandPopupWidget()
    sample_cmds = [
        SlashCommand("/boost", "Derin akıl yürütme", "builtin", "⚡ AGY", "#00F0FF"),
        SlashCommand("/plan", "Plan modu", "builtin", "⚡ AGY", "#00F0FF"),
    ]
    popup.set_commands(sample_cmds, preselected=["/boost"])
    assert popup.selected_commands == ["/boost"]

    emitted_updates = []
    popup.commands_updated.connect(lambda c: emitted_updates.append(list(c)))

    # Click "Temizle"
    popup.clear_selection()
    assert popup.selected_commands == []
    assert emitted_updates[-1] == []

    # Confirm selection after clearing
    popup.confirm_selection()
    assert popup.selected_commands == []
    assert not popup.isVisible()
    popup.close()


def test_chat_input_field_preserves_unix_file_paths(qapp):
    """Verify that file paths like /home/user/project.py are not stripped as slash commands."""
    dummy_parent = QWidget()
    dummy_parent.bridge = AgyProcessBridge()
    input_field = ChatInputField(parent_chat=dummy_parent)

    # Input contains a Unix file path and a command
    text = "/boost /home/batu/project/main.py dosyasını analiz et"
    suffix = input_field._extract_non_command_suffix(text)
    assert "/home/batu/project/main.py dosyasını analiz et" == suffix

    input_field.close()
    dummy_parent.close()

