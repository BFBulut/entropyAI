"""
Automated Test Suite: Agent Environment Researcher & Sandbox Architectures.
=============================================================================
Agentic TDD Invariant: 100% Pass Rate Required.

Validates:
1. EnvironmentBenchmarkCatalog taxonomies, utility scoring, and comparative ranking.
2. POMDPEnvironmentFormulator Shannon belief entropy, observation density, and reward signal.
3. EnvironmentSuitabilityAdvisor recommendations across desktop GUI, web browser, microVM, Docker, and Worktree CoW.
4. EnvironmentTelemetryTracker metric ingestion and statistical summary computation.
5. ObsidianEnvironmentDossierCompiler frontmatter, Mermaid diagram, LaTeX formulas, and Markdown rendering.
6. Unified AgentEnvironmentResearchEngine end-to-end study pipeline and dossier disk export.
"""

from pathlib import Path
import pytest

from src.entropy.agent_desk.research.agent_environment_researcher import (
    EnvironmentType,
    ObservabilityType,
    StateDynamicsType,
    FeedbackBandwidthType,
    EnvironmentBenchmarkItem,
    EnvironmentBenchmarkCatalog,
    POMDPState,
    POMDPObservation,
    POMDPEnvironmentFormulator,
    EnvironmentRecommendation,
    EnvironmentSuitabilityAdvisor,
    EnvironmentSessionMetric,
    EnvironmentTelemetryTracker,
    ObsidianEnvironmentDossierCompiler,
    AgentEnvironmentResearchEngine,
)


def test_environment_benchmark_catalog_and_ranking():
    catalog = EnvironmentBenchmarkCatalog.get_catalog()
    assert len(catalog) == 7
    assert "entropy_agentdesk_cow" in catalog
    assert "e2b_firecracker" in catalog
    assert "swe_bench_docker" in catalog
    assert "web_arena_browser" in catalog
    assert "os_world_gui" in catalog
    assert "intercode_repl" in catalog
    assert "stanford_generative_office" in catalog

    entropy_item = catalog["entropy_agentdesk_cow"]
    assert entropy_item.environment_type == EnvironmentType.GIT_WORKTREE_COW
    assert entropy_item.spin_up_latency_ms < 25.0
    assert entropy_item.local_first_compliance is True
    assert entropy_item.sota_benchmark_pass_rate > 99.0

    ranked = EnvironmentBenchmarkCatalog.compare_environments()
    assert len(ranked) == 7
    assert ranked[0]["name"].startswith("Entropy AgentDesk")
    for r in ranked:
        assert 0.0 <= r["composite_utility_score"] <= 1.0


def test_pomdp_environment_formulator_metrics():
    formulator = POMDPEnvironmentFormulator()

    # 1. Belief entropy calculation
    # Pure certainty: single state prob = 1.0 -> entropy = 0.0
    entropy_certain = formulator.calculate_belief_entropy([1.0, 0.0, 0.0])
    assert entropy_certain == 0.0

    # Uniform distribution across 2 states -> entropy = 1.0 bit
    entropy_uniform = formulator.calculate_belief_entropy([0.5, 0.5])
    assert pytest.approx(entropy_uniform, 0.01) == 1.0

    # 2. Observation density
    density = formulator.calculate_observation_density(token_count=1000, duration_ms=500.0)
    assert density == 2000.0

    # 3. Step reward calculation
    # Ideal step: test passes, 0 AST errors, fast execution
    rew_clean = formulator.compute_reward_signal(
        test_exit_code=0,
        ast_errors=0,
        execution_latency_ms=100.0,
        tokens_consumed=500,
    )
    assert rew_clean > 0.9

    # Failed step: test fails, AST errors present
    rew_fail = formulator.compute_reward_signal(
        test_exit_code=1,
        ast_errors=4,
        execution_latency_ms=3000.0,
        tokens_consumed=8000,
    )
    assert rew_fail < 0.0


def test_environment_suitability_advisor():
    advisor = EnvironmentSuitabilityAdvisor()

    # Scenario 1: Desktop GUI task
    rec_gui = advisor.advise_for_task(
        task_goal="Masaüstü LibreOffice üzerinde tablo biçimlendir ve ekran görüntüsü al",
        requires_gui=True,
    )
    assert rec_gui.recommended_env == EnvironmentType.OS_DESKTOP_GUI
    assert "OSWorld" in rec_gui.recommended_item_name
    assert rec_gui.confidence_score >= 0.90

    # Scenario 2: Web browsing task
    rec_web = advisor.advise_for_task(
        task_goal="E-ticaret sitesine girip ürün fiyatlarını web scraping ile tara",
        requires_browser=True,
    )
    assert rec_web.recommended_env == EnvironmentType.HEADLESS_BROWSER
    assert "WebArena" in rec_web.recommended_item_name

    # Scenario 3: Cloud MicroVM task
    rec_microvm = advisor.advise_for_task(
        task_goal="Yabancı Python kodunu izole sandbox içinde güvenle çalıştır",
        requires_cloud_isolation=True,
        strict_local_privacy=False,
    )
    assert rec_microvm.recommended_env == EnvironmentType.MICRO_VM
    assert "E2B" in rec_microvm.recommended_item_name

    # Scenario 4: Heavy Docker build
    rec_docker = advisor.advise_for_task(
        task_goal="C++ build ve apt-get bağımlılıkları derle",
    )
    assert rec_docker.recommended_env == EnvironmentType.DOCKER_CONTAINER

    # Scenario 5: Default local multi-agent software engineering task
    rec_default = advisor.advise_for_task(
        task_goal="Otonom ajan ortamları ile alakalı araştırma yap ve kod yaz",
        strict_local_privacy=True,
    )
    assert rec_default.recommended_env == EnvironmentType.GIT_WORKTREE_COW
    assert "AgentDesk" in rec_default.recommended_item_name
    assert rec_default.confidence_score >= 0.95


def test_environment_telemetry_tracker():
    tracker = EnvironmentTelemetryTracker()

    # Initial empty summary
    empty_summary = tracker.compute_summary()
    assert empty_summary["total_sessions"] == 0
    assert empty_summary["cleanup_success_rate_pct"] == 100.0

    # Record sessions
    s1 = EnvironmentSessionMetric(
        session_id="s1",
        env_type=EnvironmentType.GIT_WORKTREE_COW,
        spin_up_duration_ms=15.0,
        commands_executed=5,
        tests_passed_count=10,
        tests_failed_count=0,
        memory_peak_mb=5.0,
        ast_violations_caught=0,
        cleanup_successful=True,
    )
    s2 = EnvironmentSessionMetric(
        session_id="s2",
        env_type=EnvironmentType.GIT_WORKTREE_COW,
        spin_up_duration_ms=25.0,
        commands_executed=3,
        tests_passed_count=8,
        tests_failed_count=2,
        memory_peak_mb=7.0,
        ast_violations_caught=1,
        cleanup_successful=True,
    )
    tracker.record_session(s1)
    tracker.record_session(s2)

    summary = tracker.compute_summary()
    assert summary["total_sessions"] == 2
    assert summary["avg_spin_up_ms"] == 20.0
    assert summary["pass_rate_pct"] == 90.0
    assert summary["cleanup_success_rate_pct"] == 100.0
    assert summary["ast_violations_total"] == 1


def test_obsidian_environment_dossier_compiler():
    compiler = ObsidianEnvironmentDossierCompiler()
    dossier = compiler.compile_dossier(
        title="Otonom Ajan Ortamları Raporu",
        researcher_name="Deep Researcher",
    )

    assert "---" in dossier
    assert "title: \"Otonom Ajan Ortamları Raporu\"" in dossier
    assert "author: \"Deep Researcher\"" in dossier
    assert "[[AUTONOMOUS_AGENT_ARCHITECTURE_FAZ158]]" in dossier
    assert "```mermaid" in dossier
    assert "Entropy AgentDesk" in dossier
    assert "E2B MicroVM" in dossier
    assert "SWE-bench Docker" in dossier
    assert "WebArena" in dossier
    assert "OSWorld" in dossier
    assert "\\mathcal{M}_{\\text{agent}}" in dossier


def test_agent_environment_research_engine_full_flow(tmp_path):
    engine = AgentEnvironmentResearchEngine(workspace_root=str(tmp_path))

    # 1. Full research lifecycle
    res = engine.run_full_environment_study(
        task_goal="Otonom ajan ortamları araştırması ve TDD doğrulaması",
    )

    assert res["status"] == "success"
    assert res["total_environments_studied"] == 7
    assert "AgentDesk" in res["top_ranked_environment"]
    assert res["recommended_env_type"] == EnvironmentType.GIT_WORKTREE_COW.value
    assert res["confidence_score"] >= 0.95
    assert res["belief_entropy_bits"] >= 0.0
    assert res["obs_density_tokens_per_sec"] > 0
    assert res["sample_step_reward"] > 0.0
    assert res["dossier_length_chars"] > 1000

    # 2. Export dossier to disk
    export_path = tmp_path / "docs" / "reports" / "agent_envs_report.md"
    written_path = engine.export_dossier_to_disk(export_path)
    assert written_path.exists()
    content = written_path.read_text(encoding="utf-8")
    assert "Otonom Ajan Ortamları" in content
    assert "Entropy AgentDesk" in content
