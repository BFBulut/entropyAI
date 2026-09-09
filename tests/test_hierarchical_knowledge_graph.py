"""Automated test suite for Dynamic Hierarchical Constellation Knowledge Graph and Zero-Pollution Workspace."""

import re
import json
from pathlib import Path
import pytest

from entropy.core.config import config
from entropy.skills.manager import SkillManager
from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
from entropy.ui.widgets.skills_widget import SkillsWidget
from entropy.ui.widgets.knowledge_graph import KnowledgeGraphWidget, classify_report_to_hub, normalize_slug


def test_zero_pollution_project_selection(qapp, tmp_path):
    """
    Verify zero-pollution project workspace isolation:
    Selecting an external project folder (e.g. C:\\Entropy Agent Desk) must NEVER
    auto-create a 'skills/' directory or mutate the project folder in any way.
    """
    clean_project_dir = tmp_path / "Entropy Agent Desk"
    clean_project_dir.mkdir(parents=True, exist_ok=True)

    # 1. SkillManager with empty external project
    sm = SkillManager(project_dir=clean_project_dir)
    assert not (clean_project_dir / "skills").exists(), "SkillManager.__init__ must not create skills directory!"
    assert sm.project_skills_dir is None

    # Global system skills should still resolve and be active
    global_skills = sm.list_skills()
    assert len(global_skills) > 0
    assert any(s.name == "financial-auditor" for s in global_skills)

    # 2. SkillsWidget._on_project_changed simulation
    sw = SkillsWidget(skill_manager=sm)
    sw._on_project_changed(str(clean_project_dir))

    assert not (clean_project_dir / "skills").exists(), "SkillsWidget._on_project_changed must not create skills directory!"
    assert len(list(clean_project_dir.iterdir())) == 0, "Project folder must remain 100% clean and unpolluted!"
    sw.close()


def test_obsidian_project_scoped_reports(tmp_path):
    """
    Verify project-scoped and skill-scoped research report generation in Obsidian Vault:
    - project_name -> Entropy/Projects/<project_name>/Reports/<safe_title>.md
    - skill_name -> Entropy/Skills/<skill_name>/Reports/<safe_title>.md
    - fallback -> Entropy/Reports/<safe_title>.md
    - get_research_reports() recursively collects across all folders
    """
    vm = ObsidianVaultManager(vault_path=tmp_path)

    # 1. Project-scoped report
    proj_rep = vm.save_research_report(
        "Architecture Evaluation",
        "# Architecture Evaluation Content",
        project_name="Entropy Agent Desk"
    )
    expected_proj_path = tmp_path / "Entropy" / "Projects" / "Entropy Agent Desk" / "Reports" / "Architecture Evaluation.md"
    assert proj_rep == expected_proj_path
    assert expected_proj_path.exists()
    assert "project:Entropy Agent Desk" in expected_proj_path.read_text(encoding="utf-8")

    # 2. Skill-scoped report
    skill_rep = vm.save_research_report(
        "Website Design Specs",
        "# Website Specs Content",
        skill_name="website-builder"
    )
    expected_skill_path = tmp_path / "Entropy" / "Skills" / "website-builder" / "Reports" / "Website Design Specs.md"
    assert skill_rep == expected_skill_path
    assert expected_skill_path.exists()
    assert "skill:website-builder" in expected_skill_path.read_text(encoding="utf-8")

    # 3. Global fallback report
    global_rep = vm.save_research_report(
        "Global Directives Report",
        "# Global Directives Content"
    )
    expected_global_path = tmp_path / "Entropy" / "Reports" / "Global Directives Report.md"
    assert global_rep == expected_global_path
    assert expected_global_path.exists()

    # 4. Recursive collection
    all_reports = vm.get_research_reports()
    assert len(all_reports) == 3
    report_titles = [r["title"] for r in all_reports]
    assert "Architecture Evaluation" in report_titles
    assert "Website Design Specs" in report_titles
    assert "Global Directives Report" in report_titles

    # list_reports is an alias
    assert len(vm.list_reports()) == 3


def test_dynamic_skill_synthesis_and_hub_creation(tmp_path):
    """
    Verify dynamic skill synthesis and sub-hub discovery:
    Creating a new skill (e.g. website-builder) dynamically creates a sub-hub under hub-skills.
    """
    skills_dir = tmp_path / "custom_skills"
    skills_dir.mkdir()
    sm = SkillManager(root_skills_dir=skills_dir)

    # Synthesize new skill
    created = sm.create_skill(
        name="website-builder",
        description="Otomatik web sitesi oluşturma ve HTML/CSS tasarımı",
        instructions="Web siteleri oluştururken responsive CSS ve erişilebilir HTML kullan.",
        scripts={"deploy.py": "print('Deployed website')"}
    )
    assert created.name == "website-builder"
    assert (skills_dir / "website-builder" / "SKILL.md").exists()

    # Verify SkillManager lists the new skill
    skill_names = [s.name for s in sm.list_skills()]
    assert "website-builder" in skill_names

    # Clean up state file cache if needed
    sm.delete_skill("website-builder")


def test_deterministic_virtual_taxonomy():
    """
    Verify deterministic classification of existing and new reports into appropriate sub-hubs
    without physically altering or moving files on disk.
    """
    registered_skills = ["financial-auditor", "autonomous-agent", "pdf-analyzer", "website-builder"]
    known_projects = ["EntropiAI", "Entropy Agent Desk"]

    # 1. Financial Report classification
    hub, cluster, grp = classify_report_to_hub(
        title="CLO Tranche SVI Stoikov Beneish ve Multi Curve Mimarisi",
        path_str="C:/Users/batu_/OneDrive/Belgeler/Obsidian Vault/Entropy/Reports/CLO Tranche.md",
        tags=None,
        registered_skills=registered_skills,
        known_projects=known_projects
    )
    assert hub == "subhub-skill-financial-auditor"
    assert cluster == "skill:financial-auditor"
    assert grp == "skills"

    # 2. PDF Report classification
    hub, cluster, grp = classify_report_to_hub(
        title="_EKLENEN PDF BELGESİ MTAxMDYyMjczZG",
        path_str="C:/Users/batu_/OneDrive/Belgeler/Obsidian Vault/Entropy/Reports/_EKLENEN PDF.md",
        tags=None,
        registered_skills=registered_skills,
        known_projects=known_projects
    )
    assert hub == "subhub-skill-pdf-analyzer"
    assert cluster == "skill:pdf-analyzer"

    # 3. Autonomous Agent classification
    hub, cluster, grp = classify_report_to_hub(
        title="2026 Otonom Ajan Mimarileri Harness AgentDesks Faz73",
        path_str="C:/Users/batu_/OneDrive/Belgeler/Obsidian Vault/Entropy/Reports/2026 Otonom Ajan.md",
        tags=None,
        registered_skills=registered_skills,
        known_projects=known_projects
    )
    assert hub == "subhub-skill-autonomous-agent"
    assert cluster == "skill:autonomous-agent"

    # 4. Project-Scoped path classification
    hub, cluster, grp = classify_report_to_hub(
        title="Custom Report",
        path_str="C:/Entropy/Projects/Entropy_Agent_Desk/Reports/Custom.md",
        tags=None,
        registered_skills=registered_skills,
        known_projects=known_projects
    )
    assert hub == "subhub-project-entropy-agent-desk"
    assert cluster == "project:entropy-agent-desk"
    assert grp == "projects"

    # 5. Future dynamic skill (website-builder) classification
    hub, cluster, grp = classify_report_to_hub(
        title="Modern Website Landing Page Mimarisi",
        path_str="C:/Entropy/Reports/Website.md",
        tags=["website-builder"],
        registered_skills=registered_skills,
        known_projects=known_projects
    )
    assert hub == "subhub-skill-website-builder"
    assert cluster == "skill:website-builder"


def test_multi_hub_hierarchy_and_scope_filtering(qapp, tmp_path):
    """
    Verify the 4-hub constellation graph hierarchy, initial seed layout, and Scope Selector:
    - 4 Main Category Hubs (hub-projects, hub-skills, hub-mcp, hub-cognitive)
    - Default scope is '🌐 Tüm Hafıza (Galaksi Görünümü)'
    - Switching scope updates widget.current_scope cleanly
    """
    vm = ObsidianVaultManager(vault_path=tmp_path)
    vm.save_research_report("Finansal_Rapor_Test", "# Finansal Test", tags=["finansal"])
    vm.save_research_report("Project_Core_Report", "# Project Core", project_name="EntropiAI")

    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    nodes = graph["nodes"]
    links = graph["links"]

    # 1. Verify Central Ego Core exists
    ego = next((n for n in nodes if n["id"] == "ego-entropy-core"), None)
    assert ego is not None
    assert ego["val"] == 22
    assert ego["x"] == 0 and ego["y"] == 0

    # 2. Verify 4 Category Hubs exist
    hub_ids = [n["id"] for n in nodes if n["group"] == "hub"]
    assert "hub-projects" in hub_ids
    assert "hub-skills" in hub_ids
    assert "hub-mcp" in hub_ids
    assert "hub-cognitive" in hub_ids

    # 3. Verify Sub-Hubs under Category Hubs
    subhub_skills = [n["id"] for n in nodes if n["group"] == "skill"]
    assert "subhub-skill-financial-auditor" in subhub_skills
    assert "subhub-skill-autonomous-agent" in subhub_skills

    subhub_mcps = [n["id"] for n in nodes if n["group"] == "mcp"]
    assert any("obsidian" in s for s in subhub_mcps)

    # 4. Verify Tree Links
    tree_links = [l for l in links if l.get("is_tree_link")]
    assert len(tree_links) > 0

    # 5. Verify Scope Selector combo box
    assert widget.scope_combo.count() >= 6
    # Default item must be Galaxy view
    assert widget.scope_combo.itemText(0) == "🌐 Tüm Hafıza (Galaksi Görünümü)"
    assert widget.scope_combo.itemData(0) == "all"
    assert widget.current_scope == "all"

    # Test applying different scopes
    widget.apply_scope("all_skills")
    assert widget.current_scope == "all_skills"

    widget.apply_scope("skill:financial-auditor")
    assert widget.current_scope == "skill:financial-auditor"

    widget.apply_scope("all_mcp")
    assert widget.current_scope == "all_mcp"

    widget.apply_scope("all")
    assert widget.current_scope == "all"

    widget.close()


def test_decoupled_catalog_springs(tmp_path):
    """
    Verify that links extracted from master catalog index files (BELLEK_HARITASI, MEMORY)
    are marked with is_catalog_link=True to decouple physical spring tension.
    """
    entropy_dir = tmp_path / "Entropy"
    entropy_dir.mkdir(parents=True)
    moc_file = entropy_dir / "BELLEK_HARITASI.md"
    moc_file.write_text("# BELLEK HARİTASI\n- [[Note_A]]\n- [[Note_B]]\n- [[Note_C]]\n", encoding="utf-8")

    (entropy_dir / "Note_A.md").write_text("# Note A\nReference to [[Note_B]].\n", encoding="utf-8")
    (entropy_dir / "Note_B.md").write_text("# Note B\nNo links.\n", encoding="utf-8")
    (entropy_dir / "Note_C.md").write_text("# Note C\nNo links.\n", encoding="utf-8")

    vm = ObsidianVaultManager(vault_path=tmp_path)
    graph_data = vm.build_knowledge_graph()
    links = graph_data["links"]

    moc_links = [l for l in links if "BELLEK_HARITASI" in l["source"]]
    assert len(moc_links) == 3
    for l in moc_links:
        assert l.get("is_catalog_link") is True, "Catalog links must be flagged as is_catalog_link=True!"

    # Normal note links should not be flagged as catalog
    note_a_links = [l for l in links if "Note_A" in l["source"]]
    assert len(note_a_links) == 1
    assert note_a_links[0].get("is_catalog_link") is False


def test_initial_orbital_seed_layout(qapp, tmp_path):
    """
    Verify anti-squish seed layout:
    All nodes must have numeric seed coordinates placed in distinct constellation clusters.
    """
    vm = ObsidianVaultManager(vault_path=tmp_path)
    for i in range(10):
        vm.save_research_report(f"Seed_Test_{i}", f"# Content {i}", tags=["seed"])

    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    nodes = graph["nodes"]

    for n in nodes:
        assert "x" in n and "y" in n, f"Node {n['id']} must have pre-computed seed coordinates!"
        assert isinstance(n["x"], (int, float))
        assert isinstance(n["y"], (int, float))

    # Verify 4 Category Hubs are in 4 distinct quadrants (not all clustered at origin)
    hub_projects = next(n for n in nodes if n["id"] == "hub-projects")
    hub_skills = next(n for n in nodes if n["id"] == "hub-skills")
    hub_mcp = next(n for n in nodes if n["id"] == "hub-mcp")
    hub_cog = next(n for n in nodes if n["id"] == "hub-cognitive")

    assert hub_projects["x"] < 0 and hub_projects["y"] < 0  # Top-Left
    assert hub_skills["x"] > 0 and hub_skills["y"] < 0    # Top-Right
    assert hub_mcp["x"] > 0 and hub_mcp["y"] > 0          # Bottom-Right
    assert hub_cog["x"] < 0 and hub_cog["y"] > 0          # Bottom-Left

    widget.close()


def test_obsidian_project_scoped_reports_positional(tmp_path):
    """
    Verify positional call signature save_research_report(title, content, project_name, skill_name)
    accurately assigns project and skill instead of dropping or confusing arguments.

    Hedef klasör kuralı 2026-09-09'da tersine çevrildi: YETENEK, projeden önce
    gelir. Gerekçe ölçüldü (gerçek kasa): proje öncelikli olduğu sürece yetenek
    atıflı 77 rapor Projects/*/Reports/ altına düşüyor ve yordam damıtma onları
    kaynak olarak göremiyordu (google-flow "kaynak yok", financial-auditor
    104/104 "güncel"). Proje bağlamı `project:` etiketiyle korunur; her iki
    konumlu argüman da hâlâ doğru alana bağlanır.
    """
    vm = ObsidianVaultManager(vault_path=tmp_path)
    rep = vm.save_research_report("Positional_Test", "# Positional Content", "Entropy_Agent_Desk", "website-builder")
    expected_path = tmp_path / "Entropy" / "Skills" / "website-builder" / "Reports" / "Positional_Test.md"
    assert rep == expected_path
    assert expected_path.exists()
    content = expected_path.read_text(encoding="utf-8")
    assert "project:Entropy_Agent_Desk" in content
    assert "skill:website-builder" in content


def test_turkish_unicode_slug_normalization_and_virtual_taxonomy():
    """
    Verify Turkish unicode normalization in normalize_slug and deterministic classification.
    E.g., 'Geliştirme Projesi' -> 'gelistirme-projesi', 'Özel Araştırma' -> 'ozel-arastirma'.
    """
    assert normalize_slug("Geliştirme Projesi") == "gelistirme-projesi"
    assert normalize_slug("Özel_Finansal_Rapor") == "ozel-finansal-rapor"
    assert normalize_slug("---") == "item"

    registered_skills = ["financial-auditor", "autonomous-agent", "website-builder"]
    known_projects = ["Geliştirme Projesi"]

    hub, cluster, grp = classify_report_to_hub(
        title="Geliştirme Raporu",
        path_str="C:/Entropy/Projects/Geliştirme Projesi/Reports/Rapor.md",
        tags=None,
        registered_skills=registered_skills,
        known_projects=known_projects
    )
    assert hub == "subhub-project-gelistirme-projesi"
    assert cluster == "project:gelistirme-projesi"
    assert grp == "projects"


def test_dual_mode_resolution_preserves_global_and_project_skills(tmp_path):
    """
    Verify that when a workspace has its own 'skills/' folder, SkillManager(project_dir=...)
    loads BOTH global system skills (e.g. financial-auditor) AND the workspace's local skills.
    Neither should be purged or overwritten.
    """
    proj_dir = tmp_path / "ActiveWorkspace"
    proj_skills = proj_dir / "skills"
    proj_skills.mkdir(parents=True, exist_ok=True)

    # Create workspace-local skill
    local_skill_dir = proj_skills / "workspace-linter"
    local_skill_dir.mkdir()
    (local_skill_dir / "SKILL.md").write_text(
        "---\nname: workspace-linter\ndescription: Proje kodunu denetler\n---\n\n# Linter\n",
        encoding="utf-8"
    )

    sm = SkillManager(project_dir=proj_dir)
    skill_names = [s.name for s in sm.list_skills()]

    # Local skill must be discovered
    assert "workspace-linter" in skill_names
    # Global skills must also be present
    assert "financial-auditor" in skill_names
    assert "autonomous-agent" in skill_names


def test_isolation_button_and_scope_toggling(qapp, tmp_path):
    """
    Verify the KnowledgeGraphWidget isolation button exists, is checkable,
    and toggles isolation mode cleanly.
    """
    vm = ObsidianVaultManager(vault_path=tmp_path)
    widget = KnowledgeGraphWidget(vault_manager=vm)

    assert hasattr(widget, "isolate_btn")
    assert widget.isolate_btn.isCheckable()
    assert not widget.isolate_btn.isChecked()

    # Toggle isolation on and off
    widget.isolate_btn.setChecked(True)
    assert widget.isolate_btn.isChecked()

    widget.isolate_btn.setChecked(False)
    assert not widget.isolate_btn.isChecked()

    widget.close()


def test_radial_sector_separation_and_panning_fix(qapp, tmp_path):
    """
    Verify complete 90-degree radial sector separation and collision elimination:
    - autonomous-agent radiates East (theta = 0 deg, R = 420px)
    - 4 autonomous subbranches cascade further East (R in [600, 850], y in [-140, +140])
    - financial-auditor radiates North (theta = -90 deg, R = 420px)
    - 4 financial subbranches fan out upwards (R in [600, 850], x in [-160, +160])
    - hub-projects at -145 deg (North-West)
    - hub-cognitive at +135 deg (South-West)
    - hub-mcp at +45 deg (South-East)
    - hub-skills at -45 deg (North-East) with dynamic skills at R >= 450px
    - Panning formula does not contain recursive jitter bug (panY = e.clientY - panY)
    - Leaf spacing along dendritic branches uses wide spacing formulas
    """
    import math
    from entropy.ui.widgets.knowledge_graph import GRAPH_HTML_TEMPLATE

    # 1. Verify critical panning bug is fixed in HTML template
    assert "panY = e.clientY - panStartY;" in GRAPH_HTML_TEMPLATE
    assert "panY = e.clientY - panY;" not in GRAPH_HTML_TEMPLATE

    vm = ObsidianVaultManager(vault_path=tmp_path)
    vm.save_research_report("Faz 72 Test Report", "# Faz 72", tags=["autonomous-agent"])
    vm.save_research_report("CLO Structuring Report", "# CLO", tags=["financial-auditor"])

    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    nodes = graph["nodes"]
    node_map = {n["id"]: n for n in nodes}

    # 2. Verify Central Core is at origin
    assert node_map["ego-entropy-core"]["x"] == 0
    assert node_map["ego-entropy-core"]["y"] == 0

    # 3. Autonomous Agent sector (East / Right: theta = 0 deg, R = 420px)
    agent_hub = node_map["subhub-skill-autonomous-agent"]
    assert agent_hub["x"] == 420.0
    assert agent_hub["y"] == 0.0
    r_agent = math.hypot(agent_hub["x"], agent_hub["y"])
    assert math.isclose(r_agent, 420.0, abs_tol=1.0)

    # 4. Autonomous subbranches cascade further East
    auto_sbs = [
        "subbranch-agent-faz66-80",
        "subbranch-agent-faz81-90",
        "subbranch-agent-faz91-104",
        "subbranch-agent-desks"
    ]
    for sb_id in auto_sbs:
        sb = node_map[sb_id]
        r = math.hypot(sb["x"], sb["y"])
        assert 600.0 <= r <= 860.0, f"Subbranch {sb_id} radius {r} out of [600, 860]"
        assert -140.0 <= sb["y"] <= 140.0, f"Subbranch {sb_id} y={sb['y']} out of [-140, +140]"
        assert sb["x"] >= 600.0, f"Subbranch {sb_id} x={sb['x']} must be >= 600 (East)"

    # 5. Financial Auditor sector (North / Up: theta = -90 deg, R = 420px)
    fin_hub = node_map["subhub-skill-financial-auditor"]
    assert fin_hub["x"] == 0.0
    assert fin_hub["y"] == -420.0
    r_fin = math.hypot(fin_hub["x"], fin_hub["y"])
    assert math.isclose(r_fin, 420.0, abs_tol=1.0)

    # 6. Financial subbranches fan out upwards
    fin_sbs = [
        "subbranch-fin-clo-credit",
        "subbranch-fin-vol-options",
        "subbranch-fin-defi-arb",
        "subbranch-fin-risk-alm"
    ]
    for sb_id in fin_sbs:
        sb = node_map[sb_id]
        r = math.hypot(sb["x"], sb["y"])
        assert 600.0 <= r <= 860.0, f"Subbranch {sb_id} radius {r} out of [600, 860]"
        assert -160.0 <= sb["x"] <= 160.0, f"Subbranch {sb_id} x={sb['x']} out of [-160, +160]"
        assert sb["y"] <= -600.0, f"Subbranch {sb_id} y={sb['y']} must be <= -600 (North)"

    # 7. Verify 90-degree separation between Agent and Financial Auditor
    agent_angle = math.atan2(agent_hub["y"], agent_hub["x"])
    fin_angle = math.atan2(fin_hub["y"], fin_hub["x"])
    angle_diff_deg = abs(math.degrees(agent_angle - fin_angle))
    assert math.isclose(angle_diff_deg, 90.0, abs_tol=1.0), f"Expected 90 deg separation, got {angle_diff_deg}"

    # 8. Category Hubs quadrant and radial verification
    hub_projects = node_map["hub-projects"]
    assert hub_projects["x"] < 0 and hub_projects["y"] < 0  # North-West
    assert math.isclose(math.hypot(hub_projects["x"], hub_projects["y"]), 400.0, abs_tol=1.0)

    hub_cog = node_map["hub-cognitive"]
    assert hub_cog["x"] < 0 and hub_cog["y"] > 0  # South-West
    assert math.isclose(math.hypot(hub_cog["x"], hub_cog["y"]), 400.0, abs_tol=1.0)

    hub_mcp = node_map["hub-mcp"]
    assert hub_mcp["x"] > 0 and hub_mcp["y"] > 0  # South-East
    assert math.isclose(math.hypot(hub_mcp["x"], hub_mcp["y"]), 400.0, abs_tol=1.0)

    hub_skills = node_map["hub-skills"]
    assert hub_skills["x"] > 0 and hub_skills["y"] < 0  # North-East
    assert math.isclose(math.hypot(hub_skills["x"], hub_skills["y"]), 400.0, abs_tol=1.0)

    # 9. Verify leaf report positions are well-spaced along their subbranch
    faz72_node = next(n for n in nodes if "Faz 72" in n["name"])
    parent_sb = node_map[faz72_node["parent_hub"]]
    leaf_dist = math.hypot(faz72_node["x"] - parent_sb["x"], faz72_node["y"] - parent_sb["y"])
    assert leaf_dist >= 35.0, f"Leaf distance {leaf_dist} too small, expected >= 35.0px"

    widget.close()


def test_cognitive_memory_subbranches_and_zero_overlap(qapp, tmp_path):
    """
    Verify that cognitive memory nodes are distributed into non-overlapping subbranches:
    - subbranch-cog-sem-core, subbranch-cog-sem-arch, subbranch-cog-sem-research, subbranch-cog-sem-finance
    - Subbranches are children of subhub-cog-semantic
    - Zero pairwise node overlaps exist in the entire unified graph
    - GRAPH_HTML_TEMPLATE contains isPanning physics pause and wheel pan recalibration
    """
    from entropy.ui.widgets.knowledge_graph import (
        KnowledgeGraphWidget,
        GRAPH_HTML_TEMPLATE,
        classify_cognitive_semantic_subbranch
    )

    # 1. Verify semantic classification helper
    assert classify_cognitive_semantic_subbranch("Global MEMORY decisions") == "subbranch-cog-sem-core"
    assert classify_cognitive_semantic_subbranch("Zero-API CLI ve microkernel mimarisi") == "subbranch-cog-sem-arch"
    assert classify_cognitive_semantic_subbranch("Bilanço ve portföy nakit akışı") == "subbranch-cog-sem-finance"
    assert classify_cognitive_semantic_subbranch("Genel araştırma ve özet RAG") == "subbranch-cog-sem-research"

    # 2. Verify HTML template invariants for panning stutter & zoom jumping
    assert "if (isPanning) return;" in GRAPH_HTML_TEMPLATE
    assert "panStartX = e.clientX - panX;" in GRAPH_HTML_TEMPLATE
    assert "panY = e.clientY - panStartY;" in GRAPH_HTML_TEMPLATE
    # Faz 6: yakınlaştırma tek kapıdan (`applyZoom(newZoom, ax, ay)`) geçiyor;
    # sürükleme sırasında pan yeniden kalibrasyonu korunur, çapa değişkeni
    # cx/cy yerine ax/ay. zoomIn/zoomOut merkezi, tekerlek fare konumunu verir.
    assert "function applyZoom(newZoom, ax, ay)" in GRAPH_HTML_TEMPLATE
    assert "panStartX = ax - panX;" in GRAPH_HTML_TEMPLATE
    assert "applyZoom(zoom * zoomFactor, mx, my);" in GRAPH_HTML_TEMPLATE

    # 3. Build unified graph with sample Obsidian data
    vm = ObsidianVaultManager(vault_path=tmp_path)
    vm.save_research_report("Faz 72 Test Report", "# Faz 72", tags=["autonomous-agent"])
    vm.save_research_report("CLO Structuring Report", "# CLO", tags=["financial-auditor"])

    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    nodes = graph["nodes"]
    node_map = {n["id"]: n for n in nodes}

    # 4. Verify cognitive subbranches exist and link to subhub-cog-semantic
    cog_sbs = [
        "subbranch-cog-sem-core",
        "subbranch-cog-sem-arch",
        "subbranch-cog-sem-research",
        "subbranch-cog-sem-finance"
    ]
    for sb_id in cog_sbs:
        assert sb_id in node_map, f"Missing {sb_id} in graph nodes"
        assert node_map[sb_id]["parent_hub"] == "subhub-cog-semantic"
        assert node_map[sb_id]["cluster_group"] == "cognitive"

    # 5. Verify pairwise zero node overlap across all generated nodes
    import math
    overlaps = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a = nodes[i]
            b = nodes[j]
            d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            r_sum = a.get("val", 12) + b.get("val", 12)
            if d < r_sum:
                overlaps.append((a["id"], b["id"], d, r_sum))

    assert len(overlaps) == 0, f"Found {len(overlaps)} overlapping node pairs: {overlaps[:5]}"

    widget.close()


def test_organic_radial_fan_and_bezier_synapses(qapp, tmp_path):
    """
    Verify organic AI Mind Tree radial fan clustering and Bézier synaptic rendering:
    - compute_radial_fan_leaf_pos produces multi-tier fan nebula with zero pairwise collisions
    - GRAPH_HTML_TEMPLATE contains drawCurvedLink and quadraticCurveTo
    - Hover loop filters out is_catalog_link (zero spiderwebs on MEMORY / BELLEK_HARITASI)
    - InfoBox displays specialized index catalog badge for master MOC notes
    """
    import math
    from entropy.ui.widgets.knowledge_graph import (
        KnowledgeGraphWidget,
        GRAPH_HTML_TEMPLATE,
        compute_radial_fan_leaf_pos
    )

    # 1. Test multi-tier fan coordinates for a cluster of 25 nodes
    leaves = []
    p_x, p_y = 650.0, 135.0
    branch_angle = 0.52  # ~30 deg
    for i in range(25):
        lx, ly = compute_radial_fan_leaf_pos(p_x, p_y, branch_angle, i)
        d_from_parent = math.hypot(lx - p_x, ly - p_y)
        assert d_from_parent >= 55.0, f"Leaf {i} too close to parent: {d_from_parent}"
        leaves.append((lx, ly))

    # Verify no pairwise overlap within the cluster
    for i in range(len(leaves)):
        for j in range(i + 1, len(leaves)):
            d = math.hypot(leaves[i][0] - leaves[j][0], leaves[i][1] - leaves[j][1])
            assert d >= 28.0, f"Cluster leaves {i} and {j} overlap at distance {d:.1f}"

    # 2. Verify HTML template contains curved Bézier synapses
    assert "drawCurvedLink" in GRAPH_HTML_TEMPLATE
    assert "ctx.quadraticCurveTo" in GRAPH_HTML_TEMPLATE
    assert "if (l.is_catalog_link) return;" in GRAPH_HTML_TEMPLATE
    assert "📑 İndeks Kataloğu" in GRAPH_HTML_TEMPLATE

    # 3. Build graph with 20 sample reports and verify zero overlap across the entire graph
    vm = ObsidianVaultManager(vault_path=tmp_path)
    for i in range(20):
        tag = "autonomous-agent" if i % 2 == 0 else "financial-auditor"
        vm.save_research_report(f"Organic_Report_{i}", f"# Report {i}", tags=[tag])

    widget = KnowledgeGraphWidget(vault_manager=vm)
    graph = widget.build_unified_graph()
    nodes = graph["nodes"]

    overlaps = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            a = nodes[i]
            b = nodes[j]
            d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            r_sum = a.get("val", 12) + b.get("val", 12)
            if d < r_sum:
                overlaps.append((a["id"], b["id"], d, r_sum))

    assert len(overlaps) == 0, f"Found {len(overlaps)} overlapping node pairs: {overlaps[:5]}"
    widget.close()



