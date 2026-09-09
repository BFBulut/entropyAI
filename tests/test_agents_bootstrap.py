"""
`entropy.agents.bootstrap.bootstrap_agents` testleri.

QA bulgusu: uygulama açılışta tohum ajanları kasaya yazıyor ama `.agents/agents/`
ve `.claude/agents/` altında hiçbir derleme görünmüyordu. Kök neden derlemenin
yalnızca `APP_ROOT`'a (paketlenmiş sürümde `dist/EntropyAI`) yazması ve hatanın
sessizce yutulmasıydı. Bu testler yalıtılmış tmp kasa + tmp proje kökü ile
main.py'nin çağırdığı ta kendisi olan fonksiyonu koşturur.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import entropy.core.config  # noqa: F401  (sys.modules kaydı için)
from entropy.agents.bootstrap import bootstrap_agents


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    """APP_ROOT ve default_project_path tmp'ye taşınmış izole ortam."""
    app_root = tmp_path / "app"
    project = tmp_path / "proje"
    vault = tmp_path / "vault"
    for p in (app_root, project, vault):
        p.mkdir(parents=True, exist_ok=True)

    # `entropy.core.__init__` submodül adını config nesnesiyle gölgeliyor;
    # modülün kendisine yalnızca sys.modules üzerinden erişilebiliyor.
    cfg = sys.modules["entropy.core.config"]

    monkeypatch.setattr(cfg, "APP_ROOT", app_root, raising=False)
    monkeypatch.setattr(cfg.config, "default_project_path", project, raising=False)
    monkeypatch.setattr(cfg.config, "obsidian_vault_path", vault, raising=False)
    return app_root, project, vault


def _agy(root: Path, name: str) -> Path:
    return root / ".agents" / "agents" / name / "agent.md"


def _claude(root: Path, name: str) -> Path:
    return root / ".claude" / "agents" / f"{name}.md"


def test_bootstrap_seeds_and_compiles_to_both_roots(isolated):
    app_root, project, vault = isolated

    result = bootstrap_agents(project_dir=project, vault_path=vault)

    assert result.ok, result.error
    assert result.created, "ilk açılışta tohum ajanlar yazılmalı"
    assert set(result.compiled) == set(result.created)

    for name in result.created:
        # Kasadaki kaynak
        assert (vault / "Entropy" / "Agents" / name / "AGENT.md").is_file()
        # Her iki kök, her iki sağlayıcı biçimi
        for root in (app_root, project):
            assert _agy(root, name).is_file(), f"{name} agy biçimi {root} altında yok"
            assert _claude(root, name).is_file(), f"{name} claude biçimi {root} altında yok"

    text = _agy(app_root, result.created[0]).read_text(encoding="utf-8")
    assert text.startswith("---") and "subagent: true" in text.lower()


def test_bootstrap_without_project_dir_still_writes(isolated):
    """project_dir None ise bile APP_ROOT ve ayarlardaki etkin proje yazılmalı."""
    app_root, project, vault = isolated

    result = bootstrap_agents(project_dir=None, vault_path=vault)

    assert result.ok, result.error
    assert set(result.roots) == {app_root.resolve(), project.resolve()}
    for name in result.compiled:
        assert _agy(app_root, name).is_file()
        assert _agy(project, name).is_file()


def test_bootstrap_with_invalid_project_dir_falls_back(isolated):
    app_root, project, vault = isolated

    result = bootstrap_agents(project_dir=app_root / "yok" / "boyle" / "dizin", vault_path=vault)

    assert result.ok, result.error
    assert app_root.resolve() in result.roots
    assert result.compiled


def test_bootstrap_does_not_touch_foreign_definitions(isolated):
    """Kayıt defterinde olmayan ajan dosyalarına dokunulmaz (ne silinir ne yazılır)."""
    app_root, project, vault = isolated

    distiller = _agy(app_root, "distiller")
    distiller.parent.mkdir(parents=True, exist_ok=True)
    distiller.write_text("---\nname: distiller\n---\n\n# Elle yazildi\n", encoding="utf-8")
    manual = _claude(project, "qa-build-engineer")
    manual.parent.mkdir(parents=True, exist_ok=True)
    manual.write_text("---\nname: qa-build-engineer\n---\n\n# Kullanici ajani\n", encoding="utf-8")

    before = (distiller.read_text(encoding="utf-8"), manual.read_text(encoding="utf-8"))

    result = bootstrap_agents(project_dir=project, vault_path=vault)

    assert result.ok, result.error
    assert "distiller" not in result.compiled
    assert distiller.is_file() and manual.is_file()
    assert (distiller.read_text(encoding="utf-8"), manual.read_text(encoding="utf-8")) == before


def test_bootstrap_is_idempotent_and_preserves_mtime(isolated):
    app_root, project, vault = isolated

    first = bootstrap_agents(project_dir=project, vault_path=vault)
    name = first.created[0]
    target = _agy(project, name)
    stamp = target.stat().st_mtime_ns

    second = bootstrap_agents(project_dir=project, vault_path=vault)

    assert second.created == [], "var olan ajanlar yeniden tohumlanmamalı"
    assert set(second.compiled) == set(first.compiled)
    assert target.stat().st_mtime_ns == stamp, "içerik aynıyken dosyaya yazılmamalı"


def test_bootstrap_reports_error_instead_of_raising(isolated, monkeypatch):
    _, project, vault = isolated

    def _boom(*_a, **_k):
        raise RuntimeError("kasa okunamadı")

    monkeypatch.setattr("entropy.agents.registry.AgentRegistry.ensure_defaults", _boom)

    result = bootstrap_agents(project_dir=project, vault_path=vault)

    assert not result.ok
    assert "kasa okunamadı" in (result.error or "")
    assert "başarısız" in result.summary()
