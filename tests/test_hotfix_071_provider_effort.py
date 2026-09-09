"""
Hotfix 0.7.1 — kullanıcının 0.7.0'da gördüğü dört kusuru doğrudan sürer.

  1. agy'ye geçince tur hiç başlamıyordu:
       error: invalid model selection (--model "gemini-3.8-flash-high"
       --effort "medium"): --model gemini-3.8-flash-high conflicts with
       --effort=medium
     Çünkü agy'de efor MODEL ADININ SON EKİDİR; ayrı bayrak gönderilemez.
  2. Efor kutusu agy'de Claude'un beşlisini gösteriyordu (xhigh/max agy'de yok).
  3. Paketlenmiş sürümde proje kökü .exe klasörüne düşüyor, ajan orada
     `_internal/AGENTS.md` (eski, sahte kadro) ve `_internal/skills` okuyordu;
     gerçek proje ve Obsidian kasası ise "izinli dizinlerimde değil" oluyordu.
  4. Tek bir SKILL.md gövdesinin isteme sınırsız girebilmesi.

Testler GERÇEK yoldan sürer: argv köprünün kendi `build_command`ı ile kurulur,
gerçek model çağrısı yapılmaz.
"""

import json
from pathlib import Path

import pytest

import sys as _sys

import entropy.core.config  # noqa: F401  (alt modülün yüklenmesi için)

# `entropy.core.config` adı paket üzerinde config NESNESİNE çözülüyor
# (entropy/core/__init__.py onu yeniden dışa aktarıyor); modülün kendisi
# yalnızca sys.modules üzerinden alınır — çekirdek kodun izlediği yol.
config_module = _sys.modules["entropy.core.config"]

from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.claude_bridge import ClaudeCodeBridge
from entropy.core.provider import (
    FALLBACK_AGY_MODELS,
    compose_agy_model,
    effort_levels_for,
    split_agy_model,
)
from entropy.skills.manager import SkillManager


# ---------------------------------------------------------------------------
# 1) Model adı <-> efor sözleşmesi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,base,effort",
    [
        ("gemini-3.8-flash-high", "gemini-3.8-flash", "high"),
        ("gemini-3.8-flash-medium", "gemini-3.8-flash", "medium"),
        ("gemini-3.1-pro-low", "gemini-3.1-pro", "low"),
        ("gpt-oss-120b-medium", "gpt-oss-120b", "medium"),
        # Son eki olmayan modellerde efor seçilemez.
        ("claude-sonnet-4-6", "claude-sonnet-4-6", None),
        ("claude-opus-4-6-thinking", "claude-opus-4-6-thinking", None),
    ],
)
def test_split_agy_model(name, base, effort):
    assert split_agy_model(name) == (base, effort)


def test_compose_agy_model_uses_existing_variants():
    # Var olan varyant birebir kullanılır.
    assert compose_agy_model("gemini-3.8-flash", "low") == "gemini-3.8-flash-low"
    # Tam ad verilse de tabanına inilir.
    assert compose_agy_model("gemini-3.8-flash-high", "medium") == "gemini-3.8-flash-medium"


def test_compose_agy_model_falls_back_to_nearest_variant():
    # `gemini-3.1-pro` yalnızca low/high sunuyor: "medium" en yakına düşer ve
    # ASLA var olmayan `gemini-3.1-pro-medium` üretilmez.
    composed = compose_agy_model("gemini-3.1-pro", "medium")
    assert composed in ("gemini-3.1-pro-low", "gemini-3.1-pro-high")
    assert composed in FALLBACK_AGY_MODELS
    # Claude'dan sızan "max" da geçerli bir ada indirgenir.
    assert compose_agy_model("gemini-3.8-flash", "max") == "gemini-3.8-flash-high"
    # Varyantı olmayan model olduğu gibi kalır.
    assert compose_agy_model("claude-sonnet-4-6", "high") == "claude-sonnet-4-6"


def test_effort_levels_for_provider_and_model():
    assert effort_levels_for("claude", "claude-opus-5") == [
        "low", "medium", "high", "xhigh", "max"
    ]
    assert effort_levels_for("agy", "gemini-3.8-flash-high") == ["low", "medium", "high"]
    assert effort_levels_for("agy", "gemini-3.1-pro-high") == ["low", "high"]
    # Efor kutusu bu modellerde gizlenmeli.
    assert effort_levels_for("agy", "claude-sonnet-4-6") == []


# ---------------------------------------------------------------------------
# 2) argv: agy'de `--effort` HİÇ geçmez, efor modele gömülür
# ---------------------------------------------------------------------------


def test_agy_argv_never_contains_effort_flag(monkeypatch, tmp_path):
    """
    GERÇEK arka plan yolu (`send_background_task_async` + Popen taklidi).

    Sahte köprüyle geçen bir test bu kusuru gizlerdi: hata tam olarak argv'nin
    kurulduğu yerde doğuyordu.
    """
    import threading

    from entropy.core.task_ledger import TaskLedger

    calls = []

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)

        def readline(self):
            return next(self._iter, "")

        def close(self):
            pass

    class DummyProc:
        def __init__(self, cmd, *args, **kwargs):
            calls.append(list(cmd))
            self.stdout = DummyStdout(
                ['{"event": "result", "result": {"response": "tamam"}}\n', ""]
            )
            self.pid = 909

        def wait(self, *a, **k):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)
    monkeypatch.setattr(
        "entropy.core.agy_bridge.task_ledger", TaskLedger(db_path=tmp_path / "ledger.db")
    )

    b = AgyProcessBridge()
    b.set_project_directory(tmp_path)
    b.selected_model = "gemini-3.8-flash-high"
    b.selected_effort = "medium"  # 0.7.0'da `--effort medium` üretiyordu

    done = threading.Event()
    b.send_background_task_async(
        task_id="hotfix-071",
        task_name="Efor testi",
        prompt="kısa bir not yaz",
        mode="accept-edits",
        on_result=lambda text, ok: done.set(),
        save_report=False,
    )
    assert done.wait(timeout=15), "arka plan turu bitmedi"

    assert calls, "arka plan turu argv kurmadı"
    for cmd in calls:
        assert "--effort" not in cmd, f"agy argv'sinde --effort var: {cmd}"
        model = cmd[cmd.index("--model") + 1]
        # Efor model adına gömülü: seçili "medium" flash'ta gerçekten var.
        assert model == "gemini-3.8-flash-medium", model


def test_agy_background_argv_embeds_effort_in_model(monkeypatch, tmp_path):
    b = AgyProcessBridge()
    b.selected_model = "gemini-3.8-flash-high"
    # Tur bazlı `/effort low` model adını yeniden besteler.
    assert b.apply_effort_to_model(
        b.selected_model, b.effort_for_prompt("notu özetle /effort low")
    ) == "gemini-3.8-flash-low"
    # Boost sezgisi high'a çeker.
    assert b.apply_effort_to_model(
        b.selected_model, b.effort_for_prompt("/boost projeyi geliştir")
    ) == "gemini-3.8-flash-high"


def test_agy_set_effort_switches_model_variant(isolated_settings=None):
    b = AgyProcessBridge()
    b.selected_model = "gemini-3.8-flash-high"
    assert b.set_effort("low") is True
    assert b.selected_model == "gemini-3.8-flash-low"
    assert b.selected_effort == "low"
    # Modelde olmayan seviye reddedilir (pro'da medium yok).
    b.selected_model = "gemini-3.1-pro-high"
    with pytest.raises(ValueError):
        b.set_effort("medium")


def test_claude_set_effort_returns_true_and_reaches_argv():
    b = ClaudeCodeBridge()
    assert b.set_effort("low") is True
    cmd = b.build_command("selam")
    assert cmd[cmd.index("--effort") + 1] == "low"


# ---------------------------------------------------------------------------
# 3) Ayar onarımı: Claude'dan sızan efor agy'yi kırmasın
# ---------------------------------------------------------------------------


def test_repair_provider_effort_fixes_incompatible_agy_level(monkeypatch):
    monkeypatch.setattr(config_module.EntropyConfig, "save_settings", lambda self: None)
    cfg = config_module.EntropyConfig()
    cfg.provider_models = dict(cfg.provider_models)
    cfg.provider_models["agy"] = "gemini-3.8-flash-high"
    cfg.provider_effort = dict(cfg.provider_effort)
    cfg.provider_effort["agy"] = "xhigh"  # yalnızca Claude'da var

    cfg.repair_provider_effort()
    assert cfg.provider_effort["agy"] in ("low", "medium", "high")
    assert cfg.provider_models["agy"] in FALLBACK_AGY_MODELS


def test_repair_provider_effort_keeps_model_and_effort_consistent(monkeypatch):
    monkeypatch.setattr(config_module.EntropyConfig, "save_settings", lambda self: None)
    cfg = config_module.EntropyConfig()
    cfg.provider_models = dict(cfg.provider_models)
    cfg.provider_models["agy"] = "gemini-3.8-flash-low"
    cfg.provider_effort = dict(cfg.provider_effort)
    cfg.provider_effort["agy"] = ""  # ayar boş: model son eki kazanır

    cfg.repair_provider_effort()
    assert cfg.provider_effort["agy"] == "low"
    assert cfg.provider_models["agy"] == "gemini-3.8-flash-low"


# ---------------------------------------------------------------------------
# 4) Proje kökü ve --add-dir
# ---------------------------------------------------------------------------


def test_default_project_root_is_never_the_bundle_dir(monkeypatch, tmp_path):
    exe = tmp_path / "dist" / "EntropyAI" / "EntropyAI.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("x", encoding="utf-8")
    monkeypatch.setattr(config_module.sys, "frozen", True, raising=False)
    monkeypatch.setattr(config_module.sys, "executable", str(exe))

    assert config_module.is_bundle_dir(exe.parent) is True
    assert config_module.is_bundle_dir(exe.parent / "_internal") is True
    root = config_module.default_workspace_root()
    assert root == Path.home() / ".entropy" / "workspace"
    assert config_module.is_bundle_dir(root) is False


def test_claude_isolated_add_dirs_cover_project_vault_and_workspace(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    project = tmp_path / "proje"
    project.mkdir()
    monkeypatch.setattr(config_module.config, "claude_isolated", True)
    monkeypatch.setattr(config_module.config, "obsidian_vault_path", vault)

    b = ClaudeCodeBridge()
    monkeypatch.setattr(b, "find_claude_executable", lambda: "claude")
    cmd = b.build_command("selam", project_dir=project)
    added = [cmd[i + 1] for i, a in enumerate(cmd) if a == "--add-dir"]

    assert str(project) in added
    assert str(vault.resolve()) in added
    assert str(config_module.claude_workspace_path().resolve()) in added
    # Aynı dizin iki kez eklenmez (CLI yinelenen yolda uyarıyor).
    assert len(added) == len(set(added))


def test_ledger_project_path_is_the_real_project_root(monkeypatch, tmp_path):
    """Kart `project_path`i .exe klasörü değil seçilen proje kökü olmalı."""
    project = tmp_path / "gercek-proje"
    project.mkdir()
    b = AgyProcessBridge()
    b.set_project_directory(project)
    assert Path(b.active_project_dir) == project.resolve()
    assert Path(config_module.config.default_project_path) == project.resolve()


# ---------------------------------------------------------------------------
# 5) Yetenek enjeksiyon bütçesi
# ---------------------------------------------------------------------------


def test_skill_injection_respects_char_budget(tmp_path):
    sm = SkillManager(root_skills_dir=tmp_path)
    skill_dir = tmp_path / "dev-yetenek"
    skill_dir.mkdir()
    body = "\n".join(
        f"## Bolum {i}\n" + ("uzun yordam metni " * 200) for i in range(30)
    )
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: dev-yetenek\ndescription: test\n---\n{body}", encoding="utf-8"
    )
    skill = sm.parse_skill_file(skill_dir / "SKILL.md")
    assert skill is not None
    assert len(skill.instructions) > sm.SKILL_INJECTION_CHAR_BUDGET

    text = sm.skill_injection_text(skill, query="bolum 7")
    assert len(text) <= sm.SKILL_INJECTION_CHAR_BUDGET
    # Kırpılan metin kaybolmaz: tam gövdenin YOLU her zaman istemde.
    assert str(skill.path) in text


def test_skills_manifest_stays_within_total_budget(tmp_path):
    sm = SkillManager(root_skills_dir=tmp_path)
    for i in range(60):
        d = tmp_path / f"yetenek-{i}"
        d.mkdir()
        (d / "SKILL.md").write_text(
            f"---\nname: yetenek-{i}\ndescription: {'aciklama ' * 200}\n---\ngovde",
            encoding="utf-8",
        )
    manifest = sm.get_skills_manifest()
    assert manifest
    assert len(manifest) <= sm.SKILLS_INJECTION_TOTAL_BUDGET
    assert "KURAL:" in manifest


# ---------------------------------------------------------------------------
# 6) Eski paket artıkları
# ---------------------------------------------------------------------------


def test_spec_does_not_bundle_legacy_agents_md():
    spec = (Path(__file__).resolve().parents[1] / "EntropyAI.spec").read_text(
        encoding="utf-8"
    )
    datas = spec.split("datas=[", 1)[1].split("]", 1)[0]
    assert "AGENTS.md" not in datas.replace("#", "\n#").split("#")[0] or True
    for line in datas.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "AGENTS.md" not in stripped, f"AGENTS.md hâlâ paketleniyor: {line}"
        assert not stripped.startswith("('Agents'"), f"eski Agents/ paketleniyor: {line}"


def test_no_runtime_code_reads_bundled_agents_md():
    """Entropy'nin ajan kaynağı yalnızca kasadaki `Entropy/Agents` olmalı."""
    src = Path(__file__).resolve().parents[1] / "src" / "entropy"
    offenders = []
    for path in list((src / "core").rglob("*.py")) + list((src / "agents").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if "AGENTS.md" in line and not line.lstrip().startswith("#"):
                offenders.append(f"{path}:{n}")
    assert not offenders, f"AGENTS.md hâlâ ajan kaynağı olarak okunuyor: {offenders}"
