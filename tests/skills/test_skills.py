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

    # Sol dock sekmeleri: Raporlar, Yetenekler, Görevler, MCP, Ajanlar
    # (Faz 5.5'te "Bugun" zaman çizelgesi ve "Bildirimler" merkezi eklendi.)
    tab_names = [zen.left_tabs.tabText(i) for i in range(zen.left_tabs.count())]
    # Faz 11-E adım 2: sekme çubuğu dikey gezinme listesine döndü (7/7 görünür)
    # ve etiketlerden emoji kaldırıldı; "Bugun" -> "Bugün" (cümle düzeni).
    for expected in ("Raporlar", "Yetenekler", "Görevler", "MCP", "Ajanlar",
                     "Bugün", "Bildirimler"):
        assert any(expected in t for t in tab_names), f"{expected} sekmesi yok: {tab_names}"
    assert zen.left_tabs.count() == 7
    assert hasattr(zen, "timeline_panel")
    assert hasattr(zen, "notification_center")
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
    zen.close()

def test_skill_import_from_local_dir_and_file(tmp_path):
    skills_dir = tmp_path / "skills"
    mgr = SkillManager(root_skills_dir=skills_dir)
    mgr.state_file = tmp_path / "skills_state.json"

    # Create an external skill directory
    ext_dir = tmp_path / "external_skill"
    ext_dir.mkdir()
    (ext_dir / "SKILL.md").write_text("---\nname: ext-tester\ndescription: External tester\n---\n# Ext", encoding="utf-8")
    scripts = ext_dir / "scripts"
    scripts.mkdir()
    (scripts / "test.py").write_text("print(1)", encoding="utf-8")

    # Import from directory
    skill = mgr.import_skill_from_source(str(ext_dir))
    assert skill is not None
    assert skill.name == "ext-tester"
    assert (skills_dir / "ext-tester" / "SKILL.md").exists()
    assert (skills_dir / "ext-tester" / "scripts" / "test.py").exists()

    # Import from direct SKILL.md file with custom name
    single_file = tmp_path / "custom_skill.md"
    single_file.write_text("---\nname: single-file\ndescription: Single file skill\n---\n# Single", encoding="utf-8")
    skill2 = mgr.import_skill_from_source(str(single_file), custom_name="renamed-skill")
    assert skill2 is not None
    assert skill2.name == "renamed-skill"
    assert (skills_dir / "renamed-skill" / "SKILL.md").exists()

def test_skill_auto_detection(tmp_path):
    skills_dir = tmp_path / "skills"
    mgr = SkillManager(root_skills_dir=skills_dir)
    mgr.state_file = tmp_path / "skills_state.json"

    mgr.create_skill(
        name="solidity-auditor",
        description="Solidity akıllı sözleşme güvenlik ve reentrancy analizi",
        instructions="# Auditor instructions"
    )

    detected = mgr.auto_detect_skill_for_prompt("Bu akıllı sözleşmede reentrancy açığı var mı?")
    assert detected is not None
    assert detected.name == "solidity-auditor"

    detected_none = mgr.auto_detect_skill_for_prompt("Bugün hava nasıl?")
    assert detected_none is None

def test_chat_mode_project_switching(qapp, tmp_path):
    bridge = AgyProcessBridge()
    chat = ChatModeWindow(bridge=bridge)
    chat.show()

    assert hasattr(chat, "project_btn")
    new_dir = tmp_path / "new_project"
    new_dir.mkdir()

    bridge.set_project_directory(str(new_dir))
    assert Path(new_dir).name in chat.project_btn.text()

    chat.close()

def test_skill_auto_detection_turkish_normalization(tmp_path):
    skills_dir = tmp_path / "skills"
    mgr = SkillManager(root_skills_dir=skills_dir)
    mgr.state_file = tmp_path / "skills_state.json"

    mgr.create_skill(
        name="financial-auditor",
        description="Mali tablolar, bilanço ve nakit akım denetimi",
        instructions="# Financial instructions"
    )
    mgr.create_skill(
        name="pdf-analyzer",
        description="PDF ve doküman inceleme",
        instructions="# PDF instructions"
    )
    mgr.create_skill(
        name="skill-creator",
        description="Yeni yetenek ve araç oluşturma",
        instructions="# Skill creator instructions"
    )

    # Turkish prompt with suffixes and non-ascii characters
    detected1 = mgr.auto_detect_skill_for_prompt("Son çeyrek bilançosunu detaylıca incele")
    assert detected1 is not None
    assert detected1.name == "financial-auditor"

    detected2 = mgr.auto_detect_skill_for_prompt("Bu PDF dokümanını oku ve özet çıkar")
    assert detected2 is not None
    assert detected2.name == "pdf-analyzer"

    detected3 = mgr.auto_detect_skill_for_prompt("Proje için yeni bir yetenek oluştur")
    assert detected3 is not None
    assert detected3.name == "skill-creator"

def test_skill_import_from_repo_with_only_readme(tmp_path):
    skills_dir = tmp_path / "skills"
    mgr = SkillManager(root_skills_dir=skills_dir)
    mgr.state_file = tmp_path / "skills_state.json"

    # Create dummy repo dir with only README.md and python script (no SKILL.md)
    repo_dir = tmp_path / "crypto-tracker-repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("# Crypto Tracker\nTracks live crypto prices and liquidity pools.", encoding="utf-8")
    (repo_dir / "tracker.py").write_text("print('tracking')", encoding="utf-8")

    imported = mgr.import_skill_from_source(str(repo_dir))
    assert imported is not None
    assert "crypto" in imported.name.lower() or "tracker" in imported.name.lower()
    # Verify synthesized SKILL.md exists
    dest_skill_md = skills_dir / imported.name / "SKILL.md"
    assert dest_skill_md.exists()
    content = dest_skill_md.read_text(encoding="utf-8")
    assert "name:" in content
    assert "description:" in content

def test_multi_page_pdf_page_budget_sampling(tmp_path):
    pdf_path = tmp_path / "Multi_Page_Doc.pdf"
    writer = pypdf.PdfWriter()
    for i in range(5):
        writer.add_blank_page(width=200, height=200)
    with open(pdf_path, "wb") as f:
        writer.write(f)

    engine = PDFIngestionEngine(cache_dir=tmp_path / "cache")
    res = engine.extract_pdf_content(pdf_path)
    assert res["metadata"]["pages"] == 5
    assert len(res["pages"]) == 5

def test_extract_skill_source_from_local_directory(tmp_path):
    from entropy.skills.manager import extract_skill_source_from_text
    dummy_dir = tmp_path / "my_custom_tool"
    dummy_dir.mkdir()
    (dummy_dir / "script.py").write_text("print('hello')", encoding="utf-8")

    prompt = f"Lütfen şu yeteneği sisteme kur: {str(dummy_dir)}"
    detected_path = extract_skill_source_from_text(prompt)
    assert detected_path is not None
    assert Path(detected_path).resolve() == dummy_dir.resolve()



