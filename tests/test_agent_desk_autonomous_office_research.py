"""
Automated Test Suite: Entropy Agent Desk Autonomous Office Research Subsystem.
=============================================================================
Agentic TDD Invariant: 100% Pass Rate Required.

Validates:
1. FrameworkTaxonomy & OfficeBenchmarkCatalog SOTA comparisons and SWE-bench rankings.
2. OfficeTopologySynthesizer multi-topology synthesis & CPM Slack Borrowing model tiering.
3. WorktreeCoWPlanner Ephemeral Git Worktree isolation, contention mapping, and AST merge safety scores.
4. VerificationSentinelEngine Definition of Done (DoD) synthesis and programmatic evidence verification.
5. CognitiveEnergyManager token consumption, energy decay, XP progression, and coffee break replenishment.
6. ObsidianResearchDossierCompiler YAML frontmatter, wikilinks, mermaid diagram, and markdown rendering.
7. Unified AutonomousOfficeResearchEngine end-to-end pipeline execution and dossier disk export.
"""

import os
from pathlib import Path
import pytest

from src.entropy.agent_desk.core.models import (
    DeskRole,
    TaskStatus,
    TaskItem,
    AgentPersona,
    AgentActivityState,
)
from src.entropy.agent_desk.research.autonomous_office_researcher import (
    CollaborationTopology,
    SandboxIsolationType,
    CognitiveMemoryType,
    FrameworkTaxonomy,
    OfficeBenchmarkCatalog,
    OfficeTopologyRecommendation,
    OfficeTopologySynthesizer,
    WorktreePlanResult,
    WorktreeCoWPlanner,
    VerificationEvaluation,
    VerificationSentinelEngine,
    EnergyUpdateResult,
    CognitiveEnergyManager,
    ObsidianResearchDossierCompiler,
    AutonomousOfficeResearchEngine,
    AgentEnvironmentArchetype,
    EnvironmentActionSpace,
    EnvironmentObservationSpace,
    EnvironmentBenchmarkProfile,
    AgentEnvironmentCatalog,
    AutonomousAgentEnvironmentAnalyzer,
)


def test_office_benchmark_catalog_and_ranking():
    catalog = OfficeBenchmarkCatalog.get_catalog()
    assert "chatdev" in catalog
    assert "metagpt" in catalog
    assert "swe_agent" in catalog
    assert "openhands" in catalog
    assert "muratify_agentspace" in catalog
    assert "entropy_agent_desk" in catalog

    chatdev = catalog["chatdev"]
    assert chatdev.topology == CollaborationTopology.WATERFALL_CHAT_CHAIN
    assert chatdev.swe_bench_verified_score == 19.4

    entropy = catalog["entropy_agent_desk"]
    assert entropy.topology == CollaborationTopology.BLACKBOARD_TUPLE_SPACE
    assert entropy.sandbox_isolation == SandboxIsolationType.GIT_WORKTREE_COW
    assert entropy.cpm_slack_borrowing_support is True
    assert entropy.swe_bench_verified_score > 99.0

    ranked = OfficeBenchmarkCatalog.compare_frameworks()
    assert len(ranked) == 6
    assert ranked[0]["name"] == "Entropy AgentDesk (Faz 158/159 SOTA)"
    for r in ranked:
        assert 0.0 <= r["composite_score"] <= 1.0


def test_office_topology_synthesizer_scenarios():
    synth = OfficeTopologySynthesizer()

    # 1. Research Goal
    rec_res = synth.synthesize_topology("Otonom ajan ofisleri için literatür ve repo araştırması yap")
    assert rec_res.recommended_topology == CollaborationTopology.FEDERATED_MULTI_OFFICE
    assert any(r["role"] == DeskRole.RESEARCHER for r in rec_res.roles_roster)
    assert rec_res.estimated_token_savings_pct >= 95.0

    # 2. Security Goal
    rec_sec = synth.synthesize_topology("Sistem güvenliği ve process tree audit incelemesi")
    assert rec_sec.project_type == "devsecops_and_security"
    assert rec_sec.orchestrator_model == "claude-sonnet-4-6"

    # 3. Quant Goal
    rec_quant = synth.synthesize_topology("Bates SVJ ve SABR opsiyon risk modellemesi")
    assert rec_quant.project_type == "quantitative_finance"
    assert rec_quant.recommended_topology == CollaborationTopology.BLACKBOARD_TUPLE_SPACE

    # 4. General Software Goal
    rec_gen = synth.synthesize_topology("Kullanıcı profil yönetim modülü geliştir")
    assert len(rec_gen.roles_roster) >= 3
    assert "critical_path_slack_zero" in rec_gen.cpm_slack_strategy


def test_worktree_cow_planner_contention_and_safety():
    planner = WorktreeCoWPlanner()

    tasks = [
        TaskItem(task_id="t1", office_id="off1", title="Task 1", role_target=DeskRole.DEVELOPER),
        TaskItem(task_id="t2", office_id="off1", title="Task 2", role_target=DeskRole.DEVELOPER),
        TaskItem(task_id="t3", office_id="off1", title="Task 3", role_target=DeskRole.RESEARCHER),
    ]

    # Scenario A: Contention on shared file
    targets_contested = {
        "t1": ["src/entropy/core/state.py", "src/entropy/utils.py"],
        "t2": ["src/entropy/core/state.py"],  # Contention with t1 on state.py
        "t3": ["docs/reports/research.md"],
    }

    res_contested = planner.plan_isolation(tasks, targets_contested)
    assert res_contested.total_tasks == 3
    assert "t1" in res_contested.isolated_branches
    assert res_contested.isolated_branches["t1"] == "desk/developer/t1"
    assert len(res_contested.detected_conflicts) > 0
    assert res_contested.ast_merge_safety_score < 1.0
    # t3 has zero contention so it should merge first
    assert res_contested.recommended_merge_order[0] == "t3"

    # Scenario B: Zero contention
    targets_clean = {
        "t1": ["src/entropy/module_a.py"],
        "t2": ["src/entropy/module_b.py"],
        "t3": ["docs/reports/notes.md"],
    }
    res_clean = planner.plan_isolation(tasks, targets_clean)
    assert len(res_clean.detected_conflicts) == 0
    assert res_clean.ast_merge_safety_score == 1.0


def test_verification_sentinel_engine():
    sentinel = VerificationSentinelEngine()

    # 1. DoD Synthesis by Role
    dod_res = sentinel.synthesize_dod_for_role(DeskRole.RESEARCHER, "Ajan ofisleri araştırması")
    assert len(dod_res) >= 3
    assert any("rapor" in d.lower() for d in dod_res)

    dod_dev = sentinel.synthesize_dod_for_role(DeskRole.DEVELOPER, "Kodlama")
    assert any("kod" in d.lower() for d in dod_dev)

    # 2. Verification Command
    cmd_dev = sentinel.get_verification_command(DeskRole.DEVELOPER)
    assert "pytest" in cmd_dev

    cmd_res = sentinel.get_verification_command(DeskRole.RESEARCHER)
    assert "python" in cmd_res

    # 3. Evidence Evaluation Pass
    task = TaskItem(
        task_id="t_sentinel",
        office_id="off1",
        title="Araştırma Raporu",
        role_target=DeskRole.RESEARCHER,
        acceptance_criteria=["Literatür incelendi", "Rapor derlendi"],
        definition_of_done=["Obsidian formatında çıktı alındı"],
    )

    valid_ev = sentinel.evaluate_task_evidence(
        task=task,
        evidence_text="Literatür incelendi, rapor derlendi ve Obsidian formatında kaydedildi.",
        test_exit_code=0,
    )
    assert valid_ev.ready_for_completion is True
    assert valid_ev.evidence_verified is True
    assert valid_ev.verification_score >= 0.7

    # 4. Evidence Evaluation Fail on Non-zero Exit Code
    failed_ev = sentinel.evaluate_task_evidence(
        task=task,
        evidence_text="Her şey hazır.",
        test_exit_code=1,
    )
    assert failed_ev.ready_for_completion is False
    assert "exit code 1" in failed_ev.diagnostic_feedback

    # 5. Evidence Evaluation Fail on Empty Evidence
    empty_ev = sentinel.evaluate_task_evidence(
        task=task,
        evidence_text="",
        test_exit_code=0,
    )
    assert empty_ev.ready_for_completion is False


def test_cognitive_energy_manager_and_gamification():
    manager = CognitiveEnergyManager()

    agent = AgentPersona(
        agent_id="agent_res_01",
        name="Researcher",
        office_id="off1",
        role=DeskRole.RESEARCHER,
        focus_energy_pct=100.0,
        xp=0,
        level=1,
    )

    # 1. Normal task activity
    res1 = manager.record_task_activity(agent, tokens_consumed=4000, task_complexity_weight=1.5)
    assert res1.current_energy < 100.0
    assert res1.xp_gained > 0
    assert res1.needs_coffee_break is False

    # 2. Heavy activity leading to coffee break requirement
    agent.focus_energy_pct = 25.0
    res2 = manager.record_task_activity(agent, tokens_consumed=2000)
    assert res2.needs_coffee_break is True

    # 3. Trigger coffee break
    new_energy = manager.trigger_coffee_break(agent)
    assert agent.activity_state == AgentActivityState.COFFEE_BREAK
    assert new_energy > 25.0

    # 4. XP and Level Progression
    agent.add_xp(250)
    assert agent.level >= 3
    assert "Junior Operative" in agent.specialization_badges


def test_obsidian_research_dossier_compiler():
    compiler = ObsidianResearchDossierCompiler()
    dossier = compiler.compile_dossier(
        title="Otonom Ajan Ofisi Raporu",
        researcher_name="Deep Researcher",
    )

    assert "---" in dossier
    assert "title: \"Otonom Ajan Ofisi Raporu\"" in dossier
    assert "[[AUTONOMOUS_AGENT_ARCHITECTURE_FAZ158]]" in dossier
    assert "```mermaid" in dossier
    assert "\\mathbf{Autonomous\\ Office}" in dossier
    assert "ChatDev" in dossier
    assert "MetaGPT" in dossier
    assert "Entropy AgentDesk" in dossier


def test_autonomous_office_research_engine_full_flow(tmp_path):
    engine = AutonomousOfficeResearchEngine(workspace_root=str(tmp_path))

    # 1. Full Research Pipeline
    res = engine.perform_full_research(
        goal="Otonom ajan ofisleri için araştırma yap",
        project_type="agentic_os",
    )

    assert res["status"] == "success"
    assert res["ranked_frameworks_count"] >= 5
    assert res["top_framework"] == "Entropy AgentDesk (Faz 158/159 SOTA)"
    assert res["ast_merge_safety_score"] == 1.0
    assert res["verification_ready"] is True
    assert res["dossier_length_chars"] > 500

    # 2. Export Dossier to Disk
    export_path = tmp_path / "docs" / "reports" / "test_report.md"
    written_path = engine.export_dossier_to_disk(export_path)
    assert written_path.exists()
    content = written_path.read_text(encoding="utf-8")
    assert "Otonom Ajan Ofisleri" in content


def test_agent_environment_archetypes_and_catalog():
    catalog = AgentEnvironmentCatalog.get_catalog()
    assert "swe_bench_verified" in catalog
    assert "osworld" in catalog
    assert "webarena" in catalog
    assert "openhands_sandbox" in catalog
    assert "swe_agent_aci" in catalog
    assert "intercode" in catalog
    assert "chatdev_waterfall" in catalog
    assert "entropy_agentdesk_cow" in catalog

    # Verify archetypes
    assert catalog["swe_bench_verified"].archetype == AgentEnvironmentArchetype.SWE_BENCH_CONTAINER
    assert catalog["osworld"].archetype == AgentEnvironmentArchetype.OS_DESKTOP_MULTIMODAL
    assert catalog["webarena"].archetype == AgentEnvironmentArchetype.WEB_INTERACTION_SANDBOX
    assert catalog["entropy_agentdesk_cow"].archetype == AgentEnvironmentArchetype.EPHEMERAL_WORKTREE_COW

    # Entropy Desk has fast spinup and high safety
    entropy = catalog["entropy_agentdesk_cow"]
    assert entropy.spinup_latency_ms < 100.0
    assert entropy.isolation_safety_score >= 0.95
    assert entropy.multi_agent_capable is True
    assert EnvironmentActionSpace.LINDA_TUPLE_SPACE in entropy.action_space
    assert EnvironmentObservationSpace.STRUCTURED_TUPLES in entropy.observation_space


def test_autonomous_agent_environment_analyzer_metrics():
    analyzer = AutonomousAgentEnvironmentAnalyzer()

    # Test single environment analysis
    analysis = analyzer.analyze_environment("entropy_agentdesk_cow")
    assert analysis["id"] == "entropy_agentdesk_cow"
    assert 0.0 <= analysis["composite_index"] <= 1.0
    assert analysis["composite_index"] > 0.8
    assert analysis["throughput_index"] > 0.5
    assert analysis["isolation_safety_score"] >= 0.95
    assert analysis["multi_agent_capable"] is True

    # Test error handling on unknown env
    with pytest.raises(KeyError):
        analyzer.analyze_environment("unknown_virtual_matrix")

    # Test all environments ranking
    ranked = analyzer.compare_all_environments()
    assert len(ranked) >= 8
    # Highest ranked should be entropy_agentdesk_cow due to low latency, high safety, zero token overhead
    assert ranked[0]["id"] == "entropy_agentdesk_cow"
    for r in ranked:
        assert "composite_index" in r
        assert "throughput_index" in r


def test_autonomous_agent_environment_recommendations():
    analyzer = AutonomousAgentEnvironmentAnalyzer()

    # 1. Multi-agent software engineering recommendation
    rec_se = analyzer.recommend_environment_for_workload(
        workload_type="software_engineering",
        require_multi_agent=True,
        max_latency_budget_ms=1000.0,
    )
    assert rec_se["recommended_environment_id"] == "entropy_agentdesk_cow"
    assert "seçildi" in rec_se["rationale"]

    # 2. Relaxed constraints
    rec_relaxed = analyzer.recommend_environment_for_workload(
        workload_type="web_scraping",
        require_multi_agent=False,
        max_latency_budget_ms=25000.0,
    )
    assert len(rec_relaxed["all_ranked_candidates"]) >= 1


def test_environment_research_dossier_compiler():
    compiler = ObsidianResearchDossierCompiler()
    dossier = compiler.compile_environment_research_dossier(
        title="Otonom Ajan Ortamları Raporu",
        researcher_name="Deep Researcher (Gemini 3.8 Flash High)",
    )

    assert "---" in dossier
    assert "title: \"Otonom Ajan Ortamları Raporu\"" in dossier
    assert "[[AUTONOMOUS_AGENT_ARCHITECTURE_FAZ158]]" in dossier
    assert "[[MEMORY_RAG_SPECIFICATION]]" in dossier
    assert "SWE-bench Verified" in dossier
    assert "OSWorld" in dossier
    assert "WebArena" in dossier
    assert "Entropy AgentDesk" in dossier
    assert "```mermaid" in dossier
    assert "\\mathbf{Blast\\ Radius\\ Mitigation}" in dossier


def test_autonomous_office_research_engine_environments_flow(tmp_path):
    engine = AutonomousOfficeResearchEngine(workspace_root=str(tmp_path))

    # 1. Run environment research pipeline
    res = engine.research_agent_environments(
        workload_type="enterprise_software_engineering",
        export_to_disk=True,
    )

    assert res["status"] == "success"
    assert res["total_environments_analyzed"] >= 8
    assert res["top_environment"] == "Entropy AgentDesk (Worktree CoW & Linda Blackboard)"
    assert res["exported_dossier_path"] is not None
    assert Path(res["exported_dossier_path"]).exists()

    # 2. Verify content on disk
    file_content = Path(res["exported_dossier_path"]).read_text(encoding="utf-8")
    assert "Otonom Ajan Ortamları" in file_content
    assert "Linda" in file_content

