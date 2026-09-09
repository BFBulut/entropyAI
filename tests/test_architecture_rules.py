"""
Kalici mimari kural denetimi (Agent Desk <-> Entropy AI ayrimi).

Bu dosya kullaniciya soz verilen dort kurali her QA kosusunda olcer:

1. Orkestratorun DERLENMIS istemlerinde "Entropy" dizgesi gecmez
   (orkestrator Entropy AI'in varligini bilmez).
2. Orkestratorun araclari salt okunurdur (kod yazamaz, kabuk calistiramaz).
3. `Entropy/Agents` (Entropy'nin kendi ajanlari) ile
   `Entropy/Desk/Offices/<ofis>/agents` (Desk ajanlari) kesismez.
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


FORBIDDEN_BRAND = "muratify"

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
