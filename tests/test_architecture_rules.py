"""
Kalici mimari kural denetimi (Agent Desk <-> Entropy AI ayrimi).

Bu dosya kullaniciya soz verilen dort kurali her QA kosusunda olcer:

1. Orkestratorun DERLENMIS istemlerinde "Entropy" dizgesi gecmez
   (orkestrator Entropy AI'in varligini bilmez).
2. Orkestratorun araclari salt okunurdur (kod yazamaz, kabuk calistiramaz).
3. `Entropy/Agents` (Entropy'nin kendi ajanlari) ile
   `Desk/Offices/<ofis>/agents` (Desk ajanlari) kesismez.
4. Kaynaklarda ve `docs/` altinda yasakli marka adi gecmez.
"""

from pathlib import Path

import pytest

from entropy.agents.compile import (
    _TOOLS_BY_POLICY,
    ORCHESTRATOR_RULES,
    is_orchestrator,
    render_agy_agent,
    render_claude_agent,
)
from entropy.agents.desk_registry import DeskOffice, DeskRegistry


FORBIDDEN_BRAND = "".join(("mur", "atify"))  # marka adı kaynakta hiç geçmesin diye parçalı

# Orkestratorun asla erisemeyecegi araclar: yazma ve kabuk.
WRITE_TOOLS = {"edit", "write", "bash", "notebookedit", "multiedit"}


def _office(tmp_path: Path, name: str = "finans") -> tuple:
    desk = DeskRegistry(vault_path=tmp_path)
    office = desk.create(DeskOffice(name=name, purpose="Finans arastirmasi"))
    return desk, office


# ------------------------------------------- 1. istemde "Entropy" gecmemeli

def test_orchestrator_compiled_prompts_do_not_mention_entropy(tmp_path):
    desk, office = _office(tmp_path)
    spec = desk.orchestrator_spec(office)
    assert is_orchestrator(spec), "orkestrator spec'i orchestrator rolunde degil"

    for renderer in (render_agy_agent, render_claude_agent):
        text = renderer(spec)
        assert "entropy" not in text.lower(), (
            f"{renderer.__name__} ciktisinda 'Entropy' sizdi:\n{text}"
        )


def test_orchestrator_memory_path_is_office_relative(tmp_path):
    """Mutlak kasa yolu prompt'a 'Entropy' sizdirirdi; yol ofise goreli kalmali."""
    desk, office = _office(tmp_path)
    spec = desk.orchestrator_spec(office)
    mem = str(spec.memory_path or "")
    assert mem, "orkestratorun kalici not yolu yok"
    assert "entropy" not in mem.lower()
    assert not Path(mem).is_absolute(), f"mutlak yol: {mem}"


# ------------------------------------------------ 2. araclar salt okunur

def test_orchestrator_tools_are_read_only(tmp_path):
    desk, office = _office(tmp_path)
    spec = desk.orchestrator_spec(office)
    assert (spec.tools_policy or "").lower() == "read-only"

    tools = {
        t.strip().lower()
        for t in _TOOLS_BY_POLICY["read-only"].split(",")
        if t.strip()
    }
    assert tools, "read-only politikasi bos arac listesi uretti"
    assert not (tools & WRITE_TOOLS), f"orkestratore yazma araci sizdi: {tools & WRITE_TOOLS}"

    # Claude ciktisindaki `tools:` on bilgisi de ayni listeyi tasimali.
    claude = render_claude_agent(spec)
    tools_line = next(
        (ln for ln in claude.splitlines() if ln.lower().startswith("tools:")), ""
    )
    assert tools_line, "derlenmis Claude ajaninda tools satiri yok"
    for banned in WRITE_TOOLS:
        assert banned not in tools_line.lower(), f"tools satirinda {banned}"


def test_orchestrator_rules_forbid_coding_and_shell():
    joined = " ".join(ORCHESTRATOR_RULES).lower()
    assert "kod yaz" in joined, "kod yazma yasagi kuralı kayboldu"
    assert "kabuk" in joined or "komut" in joined, "kabuk komutu yasagi kayboldu"


# --------------------------------- 3. Entropy/Agents ile Desk kokleri ayri

def test_entropy_agents_and_desk_agent_roots_do_not_overlap(tmp_path):
    desk, office = _office(tmp_path)
    desk_agents = desk.agents_dir(office.name).resolve()
    entropy_agents = (Path(tmp_path) / "Entropy" / "Agents").resolve()

    assert desk_agents != entropy_agents
    assert not desk_agents.is_relative_to(entropy_agents), (
        f"Desk ajan koku Entropy/Agents altinda: {desk_agents}"
    )
    assert not entropy_agents.is_relative_to(desk_agents)
    # Desk koku sozlesmede belirtilen yerde olmali.
    assert desk_agents.parts[-3:-1] == ("Offices", office.name)


def test_desk_orchestrator_is_not_written_into_entropy_agents(tmp_path):
    desk, office = _office(tmp_path)
    desk.ensure_orchestrator(office.name)

    entropy_agents = Path(tmp_path) / "Entropy" / "Agents"
    leaked = []
    if entropy_agents.is_dir():
        leaked = [p.name for p in entropy_agents.iterdir() if p.is_dir()]
    assert leaked == [], f"Desk orkestratoru Entropy/Agents'a sizdi: {leaked}"

    desk_agents = desk.agents_dir(office.name)
    assert desk_agents.is_dir(), "Desk ajan klasoru olusmadi"
    assert any(desk_agents.iterdir()), "orkestrator Desk kokune yazilmadi"


# --------------------------------------------- 4. yasakli marka adi taramasi

def _scan(root: Path, suffixes) -> list:
    hits = []
    if not root.is_dir():
        return hits
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if FORBIDDEN_BRAND in text.lower():
            hits.append(str(path))
    return hits


def test_no_forbidden_brand_in_docs():
    """`docs/` altinda yasakli marka adi gecmez (tests/data haric tutulur)."""
    repo = Path(__file__).resolve().parents[1]
    hits = _scan(repo / "docs", {".md", ".txt", ".json", ".html"})
    assert hits == [], f"docs altinda marka kalintisi: {hits}"


def test_no_forbidden_brand_in_sources_and_spec():
    repo = Path(__file__).resolve().parents[1]
    hits = _scan(repo / "src", {".py", ".md", ".json", ".html", ".txt"})
    hits += _scan(repo / "skills", {".py", ".md", ".json", ".yaml", ".yml"})
    for spec in repo.glob("*.spec"):
        if FORBIDDEN_BRAND in spec.read_text(encoding="utf-8", errors="ignore").lower():
            hits.append(str(spec))
    assert hits == [], f"kaynaklarda marka kalintisi: {hits}"


# ======================================================================
# Faz 9 ek kurallari: kart/posta/argv/istem ayrimi.
# ======================================================================

def test_task_board_list_does_not_return_office_cards(tmp_path):
    """
    Kural (a): `TaskBoard.list()` varsayilaniyla Entropy kartlarini dondurur.

    Ofis kartlari `Desk/Offices/<ofis>/Tasks` altinda ayri kokte durur;
    Entropy panosunda gorunurlerse kullanici ofisin ic isini kendi gorevi
    sanar ve iki kadro birbirine karisir.
    """
    from entropy.agents.tasks import ALL_CARDS, TaskCard, TaskBoard

    board = TaskBoard(vault_path=tmp_path)
    board.create(TaskCard(id="entropy-1", title="Entropy karti"))
    board.create(TaskCard(id="ofis-1", title="Ofis karti", office="finans"))

    ids = [c.id for c in board.list()]
    assert ids == ["entropy-1"], f"ofis karti Entropy panosuna sizdi: {ids}"

    office_ids = [c.id for c in board.list(office="finans")]
    assert office_ids == ["ofis-1"]

    all_ids = sorted(c.id for c in board.list(office=ALL_CARDS))
    assert all_ids == ["entropy-1", "ofis-1"]


def test_entropy_inbox_rejects_instruction_and_question(tmp_path):
    """
    Kural (b): Entropy kutusuna yalnizca `report`/`status` girer.

    Yon tek yonludur: Entropy orkestratorlere talimat verir ve soru sorar;
    orkestratorler yalnizca rapor ve durum dondurur.
    """
    from entropy.agents.mailbox import (
        ENTROPY_INBOX_KINDS,
        ENTROPY_OWNER,
        Mailbox,
        MailboxScopeError,
        Message,
        text_part,
    )

    box = Mailbox(owner_kind="entropy", vault_path=tmp_path)
    for kind in ("instruction", "question"):
        with pytest.raises(MailboxScopeError):
            box.send(Message(
                from_="finans", to=ENTROPY_OWNER, kind=kind,
                parts=[text_part("deneme")],
            ))
    for kind in ENTROPY_INBOX_KINDS:
        box.send(Message(
            from_="finans", to=ENTROPY_OWNER, kind=kind,
            parts=[text_part("deneme")],
        ))


def test_isolated_claude_argv_shape(tmp_path, monkeypatch):
    """
    Kural (c): izole argv'de `--bare` YOK; `--system-prompt-file` +
    `--strict-mcp-config` VAR; cwd git deposunun disinda.
    """
    from entropy.core import claude_bridge as cb
    from entropy.core.config import config

    monkeypatch.setattr(config, "claude_isolated", True, raising=False)
    bridge = cb.ClaudeCodeBridge()
    monkeypatch.setattr(bridge, "find_claude_executable", lambda: "claude")
    cmd = bridge.build_command("merhaba", system_prompt="Sen Entropy'sin.")

    assert "--bare" not in cmd, "desteklenmeyen --bare bayragi argv'de"
    assert "--strict-mcp-config" in cmd
    assert cb.REPLACE_SYSTEM_PROMPT_FILE_FLAG in cmd, cmd
    assert "--append-system-prompt" not in cmd

    cwd = bridge.run_cwd(None)
    assert cwd, "izole kipte cwd verilmedi"
    cwd_path = Path(cwd).resolve()
    repo = Path(__file__).resolve().parents[1]
    assert not cwd_path.is_relative_to(repo), f"cwd git deposunun icinde: {cwd}"
    assert not (cwd_path / ".git").exists()


def test_system_prompt_has_no_brand_and_orchestrator_ignores_entropy(tmp_path):
    """Kural (d): marka adi istemde gecmez; orkestrator istemi Entropy'yi anmaz."""
    from entropy.memory.system_prompt import build_system_prompt

    text = build_system_prompt("chat", provider="claude", query="merhaba")
    assert FORBIDDEN_BRAND not in text.lower(), "sistem isteminde yasakli marka"

    desk, office = _office(tmp_path)
    spec = desk.orchestrator_spec(office)
    blob = " ".join([
        spec.prompt or "", spec.description or "", spec.role or "",
        spec.memory_path or "",
    ]).lower()
    assert "entropy" not in blob, f"orkestrator istemi Entropy'yi aniyor: {spec.name}"


def test_entropy_agents_are_not_bound_to_any_desk_office(tmp_path):
    """
    Kural (e): Entropy kadrosundaki hicbir AGENT.md `office:` tasimaz.

    Faz 3'te tohum ajanlar `office: arastirma-ofisi` ile yaziliyordu; ofis
    silinse bile alan kasada kaliyor ve ajan yetim bir ofise bagli gorunuyordu.
    """
    from entropy.agents.registry import DEFAULT_AGENTS, AgentRegistry

    bound = [a.name for a in DEFAULT_AGENTS if (getattr(a, "office", "") or "").strip()]
    assert bound == [], f"DEFAULT_AGENTS tohumunda office alani: {bound}"

    reg = AgentRegistry(vault_path=tmp_path)
    reg.seed_defaults() if hasattr(reg, "seed_defaults") else None
    written = [a.name for a in reg.list() if (getattr(a, "office", "") or "").strip()]
    assert written == [], f"kasadaki Entropy ajaninda office alani: {written}"
