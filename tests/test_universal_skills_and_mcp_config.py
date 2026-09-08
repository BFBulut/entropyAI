"""
Evrensel yetenek keşfi ve MCP yapılandırma yönetimi testleri.

Doğrulanan davranış:
- discover_skill_dirs bütün CLI yerleşimlerini (Antigravity/.agents, Claude,
  Gemini, Cursor, agent-skills) öncelik sırasıyla toplar.
- Ön bilgisi olmayan SKILL.md'de yetenek adı klasör adıdır.
- Aynı ada sahip yetenekte önceliği yüksek kök kazanır (tek kayıt).
- root_skills_dir verildiğinde yalıtım korunur.
- İndirilen yetenek projenin .agents/skills dizinine düşer.
- SkillWatcher yeni bir SKILL.md görünce bus.skills_updated yayar.
- MCPManager mcp_config.json'a ekleme/güncelleme/kaldırma/aç-kapa yapar;
  yedek alır, atomik yazar, tanımadığı alanları korur.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from entropy.core.config import config
from entropy.core.event_bus import bus
from entropy.mcp.manager import MCPManager, loads_relaxed
from entropy.skills.manager import (
    GLOBAL_SKILLS_DIR,
    SkillManager,
    SkillWatcher,
    discover_skill_dirs,
)


def _write_skill(root: Path, name: str, description: str = "", with_frontmatter: bool = True) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    f = d / "SKILL.md"
    if with_frontmatter:
        f.write_text(
            f"---\nname: {name}\ndescription: \"{description or name}\"\n---\n\n# {name}\n\nTalimat.\n",
            encoding="utf-8",
        )
    else:
        f.write_text(f"# {name}\n\nOn bilgisi olmayan yetenek govdesi.\n", encoding="utf-8")
    return f


# ---------------------------------------------------------------- keşif

def test_discover_covers_every_cli_layout(tmp_path):
    """Antigravity, Claude, Gemini, Cursor ve agent-skills kökleri taranmalı."""
    for parts in (
        ("skills",),
        (".agents", "skills"),
        ("_agents", "skills"),
        (".agent", "skills"),
        (".claude", "skills"),
        (".gemini", "skills"),
        (".cursor", "skills"),
    ):
        tmp_path.joinpath(*parts).mkdir(parents=True, exist_ok=True)

    dirs = discover_skill_dirs(tmp_path)
    for parts in (
        ("skills",),
        (".agents", "skills"),
        ("_agents", "skills"),
        (".agent", "skills"),
        (".claude", "skills"),
        (".gemini", "skills"),
        (".cursor", "skills"),
    ):
        assert tmp_path.joinpath(*parts) in dirs, parts


def test_project_root_outranks_app_bundled_skills(tmp_path):
    """Öncelik: proje kökü > kullanıcı dizinleri > uygulama içi skills/."""
    proj_dir = tmp_path / ".agents" / "skills"
    proj_dir.mkdir(parents=True)
    (tmp_path / "skills").mkdir()
    dirs = discover_skill_dirs(tmp_path)

    assert dirs[0] == tmp_path / "skills"
    assert dirs[1] == proj_dir

    home = Path.home()
    project_idx = [i for i, d in enumerate(dirs) if tmp_path in d.parents]
    # tmp_path da ev dizininin altında olabildiği için proje yolları elenir.
    home_idx = [
        i for i, d in enumerate(dirs)
        if d.parent.parent == home or d.parent.parent.parent == home
    ]
    assert project_idx and home_idx
    assert max(project_idx) < min(home_idx), "proje kökleri kullanıcı dizinlerinden önce gelmeli"

    # Uygulamayla gelen skills/ en sona alınır — kendisi zaten bir proje kökü
    # değilse (geliştirme makinesinde cwd == APP_ROOT olabiliyor).
    is_project_root = any(
        GLOBAL_SKILLS_DIR == Path(r).joinpath("skills")
        for r in (Path.cwd(), config.default_project_path) if r
    )
    if GLOBAL_SKILLS_DIR in dirs and not is_project_root:
        assert dirs.index(GLOBAL_SKILLS_DIR) == len(dirs) - 1


def test_skill_without_frontmatter_takes_folder_name(tmp_path):
    _write_skill(tmp_path, "kod-gozden-gecirici", with_frontmatter=False)
    mgr = SkillManager(root_skills_dir=tmp_path)
    names = [s.name for s in mgr.list_skills()]
    assert names == ["kod-gozden-gecirici"]


def test_downloaded_skill_visible_via_project_claude_dir(tmp_path):
    """.claude/skills'e düşen bir SKILL.md panelde ve yönlendirmede görünmeli."""
    _write_skill(tmp_path / ".claude" / "skills", "sozlesme-analisti", "Sozlesme metinlerini inceler")
    mgr = SkillManager(project_dir=tmp_path)
    names = [s.name for s in mgr.list_skills()]
    assert "sozlesme-analisti" in names


def test_same_name_keeps_only_highest_priority_entry(tmp_path):
    _write_skill(tmp_path / ".agents" / "skills", "cift-kayit", "oncelikli surum")
    _write_skill(tmp_path / ".cursor" / "skills", "cift-kayit", "ikincil surum")

    mgr = SkillManager(project_dir=tmp_path)
    hits = [s for s in mgr.list_skills() if s.name == "cift-kayit"]
    assert len(hits) == 1
    assert "oncelikli" in hits[0].description


def test_isolated_root_still_isolated(tmp_path):
    """root_skills_dir verildiğinde başka hiçbir kök taranmamalı."""
    iso = tmp_path / "iso"
    _write_skill(iso, "yalnizca-bu", "izole")
    _write_skill(tmp_path / ".agents" / "skills", "disarda", "gorunmemeli")

    mgr = SkillManager(root_skills_dir=iso)
    assert [s.name for s in mgr.list_skills()] == ["yalnizca-bu"]


def test_url_import_lands_in_project_agents_skills(tmp_path):
    """URL'den indirilen yetenek proje .agents/skills/<ad>/SKILL.md olmalı."""
    mgr = SkillManager(project_dir=tmp_path)
    payload = (
        "---\nname: web-yetenegi\ndescription: Internetten indirilen yetenek\n---\n\n# Web\n\nTalimat.\n"
    ).encode("utf-8")

    resp = MagicMock()
    resp.read.return_value = payload
    resp.__enter__.return_value = resp

    with patch("urllib.request.urlopen", return_value=resp):
        skill = mgr.download_skill_from_url("https://example.com/SKILL.md")

    assert skill is not None
    assert (tmp_path / ".agents" / "skills" / "web-yetenegi" / "SKILL.md").exists()
    assert "web-yetenegi" in [s.name for s in mgr.list_skills()]


def test_new_skill_reaches_slash_commands(tmp_path):
    from entropy.core.slash_commands import get_dynamic_skill_commands

    _write_skill(tmp_path / ".agents" / "skills", "slash-gorunur", "Slash listesinde gorunmeli")
    names = [c.name for c in get_dynamic_skill_commands(tmp_path)]
    assert "/slash-gorunur" in names


def test_new_skill_is_routable(tmp_path):
    _write_skill(tmp_path / ".agents" / "skills", "kripto-denetleyici",
                 "Kripto cuzdan ve zincir uzeri islem denetimi yapar")
    mgr = SkillManager(root_skills_dir=tmp_path / ".agents" / "skills")
    hit = mgr.auto_detect_skill_for_prompt("kripto cuzdan denetimi yap")
    assert hit is not None and hit.name == "kripto-denetleyici"


# ---------------------------------------------------------------- izleyici

def test_skill_watcher_emits_on_new_skill_file(qapp, tmp_path):
    watch_root = tmp_path / ".agents" / "skills"
    watch_root.mkdir(parents=True)

    watcher = SkillWatcher(project_dir=tmp_path, poll_interval_ms=1000)
    watcher.start()
    try:
        assert str(watch_root) in watcher.watched_dirs()

        seen = []
        bus.skills_updated.connect(lambda: seen.append(1))

        _write_skill(watch_root, "canli-yetenek", "Canli algilanan yetenek")
        watcher._check_now()
        assert seen, "yeni SKILL.md için skills_updated yayılmadı"

        # Değişiklik yoksa gereksiz sinyal üretilmemeli.
        seen.clear()
        watcher._check_now()
        assert not seen
    finally:
        watcher.stop()


# ---------------------------------------------------------------- MCP

@pytest.fixture
def mcp(tmp_path, monkeypatch):
    """Gerçek kullanıcı yapılandırmasına dokunmayan bir MCPManager."""
    cfg = tmp_path / "mcp_config.json"
    mgr = MCPManager()
    monkeypatch.setattr(mgr, "config_paths", lambda: [cfg])
    monkeypatch.setattr(mgr, "write_config_paths", lambda: [cfg])
    mgr.invalidate_cache()
    yield mgr, cfg
    mgr.invalidate_cache()


def _servers(cfg: Path):
    return json.loads(cfg.read_text(encoding="utf-8"))["mcpServers"]


def test_mcp_add_stdio_and_http(mcp):
    mgr, cfg = mcp
    assert mgr.add_server("github-tools", "stdio", "npx -y @modelcontextprotocol/server-github")
    assert mgr.add_server("uzak", "http", "https://mcp.example.com/mcp")

    data = _servers(cfg)
    assert data["github-tools"]["command"] == "npx"
    assert data["github-tools"]["args"] == ["-y", "@modelcontextprotocol/server-github"]
    assert data["uzak"] == {"serverUrl": "https://mcp.example.com/mcp"}

    names = {s["name"]: s for s in mgr.list_servers(force_refresh=True)}
    assert names["uzak"]["type"] == "http"
    assert names["github-tools"]["type"] == "stdio"
    assert names["github-tools"]["status"] == "enabled"


def test_mcp_url_is_autodetected_and_env_written(mcp):
    mgr, cfg = mcp
    mgr.add_server("otomatik", "stdio", "https://mcp.example.com/sse")
    assert _servers(cfg)["otomatik"] == {"serverUrl": "https://mcp.example.com/sse"}

    mgr.add_server("envli", "stdio", "python server.py", env={"API_KEY": "x1"})
    assert _servers(cfg)["envli"]["env"] == {"API_KEY": "x1"}


def test_mcp_validation_rejects_bad_input(mcp):
    mgr, _ = mcp
    with pytest.raises(ValueError):
        mgr.add_server("gecersiz ad", "stdio", "npx paket")
    with pytest.raises(ValueError):
        mgr.add_server("bos", "stdio", "   ")
    with pytest.raises(ValueError):
        mgr.add_server("urlsiz", "http", "npx paket")


def test_mcp_toggle_writes_disabled_flag(mcp):
    mgr, cfg = mcp
    mgr.add_server("kapanabilir", "stdio", "npx -y paket")

    assert mgr.disable_server("kapanabilir")
    assert _servers(cfg)["kapanabilir"]["disabled"] is True
    assert {s["name"]: s["status"] for s in mgr.list_servers(force_refresh=True)}["kapanabilir"] == "disabled"

    assert mgr.enable_server("kapanabilir")
    assert "disabled" not in _servers(cfg)["kapanabilir"]
    assert mgr.enable_server("kapanabilir")  # zaten etkin: yine başarılı
    assert not mgr.toggle_server("olmayan-sunucu", False)


def test_mcp_update_preserves_unknown_fields(mcp):
    """agy'nin sözleşmesi: tanınmayan alanlar (enabledTools, timeoutSeconds) korunur."""
    mgr, cfg = mcp
    cfg.write_text(json.dumps({
        "mcpServers": {
            "eski": {
                "command": "npx",
                "args": ["-y", "eski-paket"],
                "enabledTools": ["a", "b"],
                "timeoutSeconds": 30,
            }
        }
    }), encoding="utf-8")

    assert mgr.update_server("eski", server_type="stdio", command_or_url="npx -y yeni-paket")
    entry = _servers(cfg)["eski"]
    assert entry["args"] == ["-y", "yeni-paket"]
    assert entry["enabledTools"] == ["a", "b"]
    assert entry["timeoutSeconds"] == 30


def test_mcp_update_can_rename_and_switch_type(mcp):
    mgr, cfg = mcp
    mgr.add_server("yerel", "stdio", "npx -y paket")
    assert mgr.update_server(
        "yerel", server_type="http", command_or_url="https://mcp.example.com/mcp", new_name="uzaga-tasindi"
    )
    data = _servers(cfg)
    assert "yerel" not in data
    assert data["uzaga-tasindi"] == {"serverUrl": "https://mcp.example.com/mcp"}
    assert not mgr.update_server("hic-yok", command_or_url="npx x")


def test_mcp_remove_and_backup(mcp):
    mgr, cfg = mcp
    mgr.add_server("silinecek", "stdio", "npx -y paket")
    mgr.add_server("kalacak", "stdio", "npx -y baska")

    assert mgr.remove_server("silinecek")
    data = _servers(cfg)
    assert "silinecek" not in data and "kalacak" in data
    assert cfg.with_suffix(cfg.suffix + ".bak").exists()
    assert not mgr.remove_server("silinecek")


def test_mcp_relaxed_config_parsing(mcp):
    """agy yorumlu ve sonda virgüllü mcp_config.json'u kabul ediyor; biz de."""
    mgr, cfg = mcp
    cfg.write_text(
        '{\n  // yorum satiri\n  "mcpServers": {\n    /* blok */\n'
        '    "yorumlu": {"command": "npx", "args": ["-y", "p"]},\n  }\n}\n',
        encoding="utf-8",
    )
    names = [s["name"] for s in mgr.list_servers(force_refresh=True)]
    assert "yorumlu" in names
    assert loads_relaxed('{"a": 1,}')["a"] == 1


def test_mcp_config_paths_point_at_agy_locations():
    """Gerçek yollar: ~/.gemini/config/mcp_config.json birincil, eski konum yedek."""
    mgr = MCPManager()
    paths = [str(p) for p in mgr.config_paths()]
    assert any(p.endswith(str(Path(".gemini") / "config" / "mcp_config.json")) for p in paths)
    assert any(p.endswith(str(Path(".gemini") / "antigravity" / "mcp_config.json")) for p in paths)
    assert str(mgr.write_config_paths()[0]).endswith(str(Path(".gemini") / "config" / "mcp_config.json"))
