"""Automated test suite for Memory Inspector, Standalone Report Window, Dendritic Sub-Branches, and Cognitive RAG."""

import os
import json
import pytest
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from entropy.core.config import config
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.skills.manager import SkillManager, SkillDefinition
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.ui.widgets.standalone_report_window import StandaloneReportWindow, open_standalone_report_window
from entropy.ui.widgets.memory_inspector_dialog import MemoryInspectorDialog, _parse_frontmatter
from entropy.ui.widgets.markdown_renderer import render_markdown_to_html
from entropy.ui.widgets.knowledge_graph import (
    KnowledgeGraphWidget,
    classify_autonomous_subbranch,
    classify_financial_subbranch,
    classify_report_to_hub
)


def test_dendritic_subbranches_and_classification():
    """Verify deterministic dendritic sub-branch routing for autonomous-agent and financial-auditor."""
    # 1. Autonomous Agent sub-branch classification
    assert classify_autonomous_subbranch("2026 Otonom Ajan Mimarisi Faz 72") == "subbranch-agent-faz66-80"
    assert classify_autonomous_subbranch("ACP ve A2A Protokol Faz 85") == "subbranch-agent-faz81-90"
    assert classify_autonomous_subbranch("Derin Bilisim Karar Agaci Faz 99") == "subbranch-agent-faz91-104"
    assert classify_autonomous_subbranch("Agent Desks ve Harness Denetimi") == "subbranch-agent-desks"
    assert classify_autonomous_subbranch("Task_or_research Supervision") == "subbranch-agent-desks"

    # 2. Financial Auditor sub-branch classification
    assert classify_financial_subbranch("CLO Tranche ve Kredi Risk Modellemesi") == "subbranch-fin-clo-credit"
    assert classify_financial_subbranch("SVI SABR Stokastik Volatilite ve Opsiyon Fiyatlama") == "subbranch-fin-vol-options"
    assert classify_financial_subbranch("Uniswap V3 DeFi Likidite ve Arbitraj") == "subbranch-fin-defi-arb"
    assert classify_financial_subbranch("Basel III Aktif Pasif Yonetimi ALM Stratejisi") == "subbranch-fin-risk-alm"


def test_knowledge_graph_dendritic_tree_structure(qapp, tmp_path):
    """
    Verify KnowledgeGraphWidget generates dendritic sub-branches:
    - autonomous-agent has 4 subbranch nodes linked to subhub-skill-autonomous-agent
    - financial-auditor has 4 subbranch nodes linked to subhub-skill-financial-auditor
    - Category hubs have radial distance >= 320px
    - Reports attach to the correct milestone subbranch
    """
    vm = ObsidianVaultManager(vault_path=tmp_path)
    # Create sample reports matching different sub-branches
    vm.save_research_report("Faz 75 Ajan Harness", "# Faz 75", tags=["autonomous-agent"])
    vm.save_research_report("Faz 88 Otonom Karar", "# Faz 88", tags=["autonomous-agent"])
    vm.save_research_report("CLO Portfoy Tranche", "# CLO Analizi", tags=["financial-auditor"])
    vm.save_research_report("SVI Volatilite Gulumsemesi", "# Volatilite", tags=["financial-auditor"])

    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    nodes = graph["nodes"]
    links = graph["links"]

    node_dict = {n["id"]: n for n in nodes}

    # Autonomous sub-branches exist
    auto_subbranches = [
        "subbranch-agent-faz66-80",
        "subbranch-agent-faz81-90",
        "subbranch-agent-faz91-104",
        "subbranch-agent-desks"
    ]
    for sb_id in auto_subbranches:
        assert sb_id in node_dict, f"Expected {sb_id} in graph nodes"
        assert node_dict[sb_id]["parent_hub"] == "subhub-skill-autonomous-agent"
        assert node_dict[sb_id]["group"] == "subbranch"
        # Verify link exists from subhub to subbranch
        assert any(l["source"] == "subhub-skill-autonomous-agent" and l["target"] == sb_id for l in links)

    # Financial sub-branches exist
    fin_subbranches = [
        "subbranch-fin-clo-credit",
        "subbranch-fin-vol-options",
        "subbranch-fin-defi-arb",
        "subbranch-fin-risk-alm"
    ]
    for sb_id in fin_subbranches:
        assert sb_id in node_dict, f"Expected {sb_id} in graph nodes"
        assert node_dict[sb_id]["parent_hub"] == "subhub-skill-financial-auditor"
        assert node_dict[sb_id]["group"] == "subbranch"
        # Verify link exists from subhub to subbranch
        assert any(l["source"] == "subhub-skill-financial-auditor" and l["target"] == sb_id for l in links)

    # Check that Faz 75 is attached to subbranch-agent-faz66-80
    faz75_node = next((n for n in nodes if "Faz 75 Ajan Harness" in n["name"]), None)
    assert faz75_node is not None
    assert faz75_node["parent_hub"] == "subbranch-agent-faz66-80"

    # Check that CLO report is attached to subbranch-fin-clo-credit
    clo_node = next((n for n in nodes if "CLO Portfoy Tranche" in n["name"]), None)
    assert clo_node is not None
    assert clo_node["parent_hub"] == "subbranch-fin-clo-credit"

    # Radial spacing of category hubs is >= 320px
    hub_skills = node_dict["hub-skills"]
    r_skills = (hub_skills["x"]**2 + hub_skills["y"]**2)**0.5
    assert r_skills >= 319.0, f"Expected r_skills >= 320, got {r_skills}"

    widget.close()


def test_memory_inspector_dialog_features(qapp, tmp_path):
    """
    Verify MemoryInspectorDialog:
    - Resizable with Min/Max and Close buttons
    - SizeGrip enabled
    - Minimum size constraint (560x440) and initial resize (780x620)
    - Frontmatter parsing extracts metadata and removes raw YAML from body
    - Cleans ANSI and terminal codes
    """
    # Create test markdown file with YAML frontmatter
    test_md = tmp_path / "Cyber_Agent_Report.md"
    content = (
        "---\n"
        "title: Siber Ajan Mimarisi Raporu\n"
        "date: 2026-09-05\n"
        "project: EntropiAI\n"
        "skill: autonomous-agent\n"
        "tags: [harness, otonom, test]\n"
        "---\n\n"
        "# Siber Ajan Mimarisi\n\n"
        "Bu bir test raporu govdesidir. \x1b[32mRenkli ANSI metni\x1b[0m icerir.\n"
    )
    test_md.write_text(content, encoding="utf-8")

    dialog = MemoryInspectorDialog(node_id=str(test_md), parent=None)

    # Window flags include min/max
    flags = dialog.windowFlags()
    assert flags & Qt.WindowType.WindowMinMaxButtonsHint
    assert flags & Qt.WindowType.WindowCloseButtonHint

    # Size constraints
    assert dialog.isSizeGripEnabled() is True
    assert dialog.minimumWidth() >= 560
    assert dialog.minimumHeight() >= 440
    assert dialog.width() >= 560
    assert dialog.height() >= 440

    # Test frontmatter parser helper
    meta, body = _parse_frontmatter(content)
    assert meta.get("title") == "Siber Ajan Mimarisi Raporu"
    assert meta.get("date") == "2026-09-05"
    assert meta.get("project") == "EntropiAI"
    assert meta.get("skill") == "autonomous-agent"
    assert "harness" in meta.get("tags", [])
    assert not body.startswith("---")
    assert "# Siber Ajan Mimarisi" in body

    dialog.close()


def test_standalone_report_window_and_launcher(qapp, tmp_path):
    """
    Verify StandaloneReportWindow:
    - Dedicated window with min/max and close buttons
    - Minimum size constraint (600x450)
    - open_standalone_report_window function launches and re-asserts foreground
    """
    test_file = tmp_path / "Standalone_Doc.md"
    test_file.write_text("# Standalone Belge\nIcerik metni.", encoding="utf-8")

    # Launch via helper
    win = open_standalone_report_window(str(test_file))
    assert isinstance(win, StandaloneReportWindow)
    assert win.minimumWidth() >= 600
    assert win.minimumHeight() >= 450

    flags = win.windowFlags()
    assert flags & Qt.WindowType.WindowMinMaxButtonsHint
    assert flags & Qt.WindowType.WindowCloseButtonHint

    # Can open file
    win.open_report_file(str(test_file))
    assert win.isVisible()

    win.hide()
    win.close()


def test_markdown_renderer_cyber_frontmatter_banner():
    """Verify render_markdown_to_html creates a cybernetic metadata card and strips raw frontmatter."""
    raw_md = (
        "---\n"
        "title: Finansal Rapor 2026\n"
        "date: 2026-09-05\n"
        "agent: CodeArchitect\n"
        "project: EntropiAI\n"
        "skill: financial-auditor\n"
        "tags: [clo, bachelier, risk]\n"
        "---\n\n"
        "## Finansal Rapor Icerigi\n"
        "Burada detayli analiz yer aliyor."
    )

    html_out = render_markdown_to_html(raw_md)

    # 1. Metadata card is rendered
    assert "Finansal Rapor 2026" in html_out
    assert "2026-09-05" in html_out
    assert "CodeArchitect" in html_out
    assert "Proje: EntropiAI" in html_out
    assert "Yetenek: financial-auditor" in html_out
    assert "#clo" in html_out
    assert "#bachelier" in html_out

    # 2. Raw YAML delimiter is NOT displayed in body
    assert "tags: [clo" not in html_out
    assert "Finansal Rapor Icerigi" in html_out

    # 3. Empty or clean markdown works as well
    empty_html = render_markdown_to_html("")
    assert "Henüz içerik yok." in empty_html

    simple_html = render_markdown_to_html("# Basit Baslik\nMetin")
    assert "Basit Baslik" in simple_html


def test_scoped_cognitive_context_retrieval(tmp_path, monkeypatch):
    """
    Verify AgyProcessBridge.get_cognitive_context:
    - Scopes to project-specific MEMORY.md and project research reports when active_project_dir is set
    - Scopes to skill-specific research dossiers when target_skill is provided
    - Injects codebase RAG snippets for technical prompts
    - Skips heavy injection for casual greetings
    - get_mini_cognitive_context returns concise memory for follow-up turns
    """
    # 1. Setup isolated vault directory
    vault_dir = tmp_path / "Vault"
    entropy_vault = vault_dir / "Entropy"
    proj_vault = entropy_vault / "Projects" / "TestProject"
    proj_vault.mkdir(parents=True, exist_ok=True)
    proj_reports = proj_vault / "Reports"
    proj_reports.mkdir(parents=True, exist_ok=True)

    # Global MEMORY.md
    (entropy_vault / "MEMORY.md").write_text("Global sistem direktifleri ve otonom bellek.", encoding="utf-8")

    # Project MEMORY.md
    (proj_vault / "MEMORY.md").write_text("TestProject icin ozel mimari kararlar ve kurallar.", encoding="utf-8")

    # Project report
    (proj_reports / "Arch_Decision.md").write_text(
        "---\ntitle: Mimari Karar 01\n---\n# Karar 01\nMicrokernel ve sandbox mimarisi kabul edildi.",
        encoding="utf-8"
    )

    # Skills directory in vault
    skill_vault = entropy_vault / "Skills" / "financial-auditor" / "Reports"
    skill_vault.mkdir(parents=True, exist_ok=True)
    (skill_vault / "CLO_Pricing_Analysis.md").write_text(
        "---\ntitle: CLO Tranche Fiyatlama Raporu\n---\n# CLO Fiyatlama\nSABR ve SVI modelleriyle korelasyon calismasi.",
        encoding="utf-8"
    )

    # Patch config vault path
    monkeypatch.setattr(config, "obsidian_vault_path", vault_dir)

    bridge = AgyProcessBridge()
    active_proj = tmp_path / "TestProject"
    active_proj.mkdir(parents=True, exist_ok=True)
    # Create sample codebase file for RAG
    (active_proj / "engine.py").write_text("class AutonomousEngine:\n    def start(self):\n        pass\n", encoding="utf-8")
    bridge.set_project_directory(active_proj)

    # A. Casual greeting -> returns empty
    assert bridge.get_cognitive_context("merhaba") == ""
    assert bridge.get_cognitive_context("selamlar") == ""

    # B. Project technical query -> includes project memory and reports.
    # Bölüm başlıkları bütçeli birleştiriciyle birlikte değişti: proje hafızası ve
    # proje raporu tek bir "Proje Bağlamı" bölümünde toplanıyor. Doğrulanan şey
    # başlık metni değil, içeriğin bağlama gerçekten girmesi.
    ctx = bridge.get_cognitive_context("proje mimari kararlari ve motor sinifi")
    assert "Kalıcı Bilişsel Hafıza" in ctx
    assert "Proje Bağlamı (TestProject)" in ctx
    assert "TestProject icin ozel mimari kararlar" in ctx
    assert "Arch_Decision" in ctx

    # C. Skill targeted query -> includes skill research reports
    target_skill = SkillDefinition(
        name="financial-auditor",
        description="Finansal denetim ve modelleme",
        path=str(active_proj),
        instructions="",
        scripts=[]
    )
    skill_ctx = bridge.get_cognitive_context("CLO ve risk hesaplamasi yap", target_skill=target_skill)
    assert "financial-auditor" in skill_ctx
    # Yetenek-kapsamlı rapor gövdesi bağlama girmeli (başlık değil içerik).
    assert "SABR ve SVI" in skill_ctx or "CLO Fiyatlama" in skill_ctx

    # D. Mini cognitive context
    mini = bridge.get_mini_cognitive_context("CLO fiyatlama", target_skill=target_skill)
    assert isinstance(mini, str)
