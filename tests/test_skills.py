"""Automated pytest test suite for PDF Ingestion Engine, SkillManager & UI integrations."""

import io
from pathlib import Path
import pypdf
import pytest
from unittest.mock import MagicMock, patch

from entropy.skills.pdf_engine import PDFIngestionEngine
from entropy.skills.manager import SkillManager, SkillDefinition
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.event_bus import bus
from entropy.ui.widgets.skills_widget import SkillsWidget
from entropy.ui.modes.zen_mode import ZenModeWindow
from entropy.ui.modes.chat_mode import ChatModeWindow

def create_sample_pdf(file_path: Path, pages: int = 2) -> Path:
    """Helper to generate a valid PDF file on the fly."""
    writer = pypdf.PdfWriter()
    for i in range(pages):
        writer.add_blank_page(width=200, height=200)
    
    with open(file_path, "wb") as f:
        writer.write(f)
    return file_path

def test_pdf_ingestion_engine(tmp_path):
    cache_dir = tmp_path / "pdf_cache"
    engine = PDFIngestionEngine(cache_dir=cache_dir)

    pdf_file = create_sample_pdf(tmp_path / "Finans_Raporu_2026.pdf", pages=3)
    res = engine.extract_pdf_content(pdf_file)

    assert res["metadata"]["filename"] == "Finans_Raporu_2026.pdf"
    assert res["metadata"]["pages"] == 3
    assert Path(res["digest_path"]).exists()

    # Test full ingest and memory store
    ingest_res = engine.ingest_and_store_memory(pdf_file)
    assert ingest_res["metadata"]["pages"] == 3

def test_skill_manager_discovery_and_parsing(tmp_path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy skill
    skill_a = skills_dir / "market-analyst"
    skill_a.mkdir()
    skill_md = skill_a / "SKILL.md"
    skill_md.write_text(
        "---\nname: market-analyst\ndescription: Pazar verilerini inceler\nversion: 1.2.0\ntags: finance, market\n---\n\n# Market Analyst\n\nAdım 1...",
        encoding="utf-8"
    )
    scripts_dir = skill_a / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "calc_market.py").write_text("print('market')", encoding="utf-8")

    mgr = SkillManager(root_skills_dir=skills_dir)
    mgr.state_file = tmp_path / "skills_state.json"

    skills = mgr.list_skills()
    assert len(skills) == 1
    assert skills[0].name == "market-analyst"
    assert "Pazar verilerini inceler" in skills[0].description
    assert len(skills[0].scripts) == 1
    assert skills[0].scripts[0]["name"] == "calc_market.py"

    # Test toggle
    mgr.toggle_skill("market-analyst", False)
    assert mgr.list_skills()[0].enabled is False

    mgr.toggle_skill("market-analyst", True)
    assert mgr.list_skills()[0].enabled is True

    # Test manifest generation
    manifest = mgr.get_skills_manifest()
    assert "market-analyst" in manifest

    # Test create skill
    new_s = mgr.create_skill(
        name="custom-scraper",
        description="Scrapes product catalogs",
        instructions="# Scraper instructions",
        scripts={"scrape.py": "print('scraping')"}
    )
    assert new_s.name == "custom-scraper"
    assert (skills_dir / "custom-scraper" / "scripts" / "scrape.py").exists()

    # Test delete skill
    del_ok = mgr.delete_skill("custom-scraper")
    assert del_ok is True
    assert not (skills_dir / "custom-scraper").exists()

def test_skill_manager_download_url(tmp_path):
    skills_dir = tmp_path / "skills"
    mgr = SkillManager(root_skills_dir=skills_dir)
    mgr.state_file = tmp_path / "skills_state.json"

    fake_skill_content = (
        "---\nname: remote-downloader\ndescription: İndirilen özel yetenek\n---\n\n# Remote Skill\n\nTalimatlar..."
    ).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_skill_content
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        skill = mgr.download_skill_from_url("https://example.com/SKILL.md")
        assert skill is not None
        assert skill.name == "remote-downloader"
        assert (skills_dir / "remote-downloader" / "SKILL.md").exists()

def test_skills_widget_ui(qapp, tmp_path):
    skills_dir = tmp_path / "skills"
    mgr = SkillManager(root_skills_dir=skills_dir)
    mgr.state_file = tmp_path / "skills_state.json"
    mgr.create_skill("test-skill", "Test skill for UI", "# Instructions")

    widget = SkillsWidget(skill_manager=mgr)
    widget.show()

    assert widget.skills_layout.count() > 0
    assert hasattr(widget, "search_input")
    assert hasattr(widget, "sync_btn")

    widget.close()

def test_chat_mode_pdf_and_skill_integration(qapp, tmp_path):
    bridge = AgyProcessBridge()
    chat = ChatModeWindow(bridge=bridge)
    chat.show()

    # Verify skill combo and PDF button
    assert hasattr(chat, "skill_combo")
    assert hasattr(chat, "pdf_btn")
    assert chat.skill_combo.count() >= 1

    # Stage a PDF
    pdf_p = create_sample_pdf(tmp_path / "Test_Balance_Sheet.pdf")
    chat.stage_pdf_file(str(pdf_p))
    assert len(chat.staged_pdfs) == 1
    assert chat.attachment_bar.isVisible()
    assert "Test_Balance_Sheet" in chat.attach_label.text()

    chat._clear_staged_images()
    assert len(chat.staged_pdfs) == 0

    chat.close()

def test_zen_mode_skills_tab_and_pdf(qapp, tmp_path, monkeypatch):
    bridge = AgyProcessBridge()
    zen = ZenModeWindow(bridge=bridge)
    zen.show()

    # Verify 4 tabs in left dock
    assert zen.left_tabs.count() == 4
    tab_names = [zen.left_tabs.tabText(i) for i in range(zen.left_tabs.count())]
    assert any("Yetenekler" in t for t in tab_names)
    assert hasattr(zen, "skills_widget")
    assert hasattr(zen, "chat_pdf_btn")

    # Prevent background execution in test
    called_args = {}
    def mock_send_async(prompt, image_attachments=None, pdf_attachments=None, active_skill=None, mode="accept-edits"):
        called_args["prompt"] = prompt
        called_args["pdf_attachments"] = pdf_attachments
        return True

    monkeypatch.setattr(zen.bridge, "send_prompt_async", mock_send_async)

    # Test PDF staging
    sample_pdf = create_sample_pdf(tmp_path / "Annual_Report_2026.pdf")
    zen.stage_pdf_file(str(sample_pdf))
    assert len(zen.staged_pdfs) == 1
    assert "Annual_Report" in zen.attach_label.text()

    zen.chat_input.setText("Finans raporunu detaylı açıkla")
    zen._on_send_chat()

    assert len(called_args.get("pdf_attachments", [])) == 1
    assert "Annual_Report_2026.pdf" in called_args["pdf_attachments"][0]

    zen.close()
