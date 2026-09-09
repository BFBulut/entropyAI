"""
FAZ 6 — Agent Desk'in kendi kayıt defteri, orkestratör sözleşmesi ve komutları.

Doğrulanan kullanıcı kuralları:
  1. Desk'in kendi veri kökü var (`Entropy/Desk/Offices/...`) ve Entropy'nin
     `Entropy/Agents` kadrosunu KULLANMAZ.
  2. Tohum ofis/ajan yok; ofis açılınca orkestratörü otomatik doğar.
  3. Orkestratör kod yazmaz: derlemesinde araçlar kısıtlı, yasaklar yazılı.
  4. Orkestratör planlama çıktısıyla kendi alt ajanlarını oluşturur.
  5. Ofis ajanlarının derlenmiş tanımlarında ve plan/eval prompt'larında
     "Entropy" dizgesi GEÇMEZ (ofis tüzüğü kullanıcı metni olduğu için hariç).
  6. Entropy manifestinde ofis/orkestratör listesi ve devretme kuralı var.
  7. Harness uçtan uca: proje + kartlar + rapor Entropy gelen kutusuna.

Hiçbir test gerçek agy/claude süreci başlatmaz.
"""

import json
import threading

import pytest

from entropy.agents.compile import render_agy_agent, render_claude_agent
from entropy.agents.desk_registry import (
    DESK_SUBDIR,
    ORCHESTRATOR_AGENT,
    DeskOffice,
    DeskProject,
    DeskRegistry,
    desk_manifest,
    desk_roster,
)
from entropy.agents.harness import OfficeHarness
from entropy.agents.registry import AgentRegistry, AgentSpec
from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", tmp_path / "Vault", raising=False)
    return tmp_path / "Vault"


@pytest.fixture(autouse=True)
def clean_active_registry():
    OfficeHarness._active.clear()
    yield
    OfficeHarness._active.clear()


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture
def desk(vault):
    return DeskRegistry(vault_path=vault)


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


class _ScriptedBridge:
    """Sırayla hazır yanıt döndüren köprü (gerçek sözleşmenin altkümesi)."""

    provider_name = "agy"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self._lock = threading.RLock()

    def send_background_task_async(self, task_id, task_name, prompt, mode=None,
                                   on_result=None, save_report=True, agent=None,
                                   needs_write=None, project_path=None, **kw):
        with self._lock:
            self.calls.append({"task_id": task_id, "agent": agent, "prompt": prompt,
                               "project_path": project_path})
            text, ok = "", False
            for idx, (matcher, body, good) in enumerate(self.responses):
                if matcher in task_id:
                    self.responses.pop(idx)
                    text, ok = body, good
                    break
        if on_result is not None:
            on_result(text, ok)
        return task_id

    def terminate_background_task(self, task_id):
        return True


def _plan(subtasks, new_agents=None):
    data = {"subtasks": subtasks}
    if new_agents:
        data["new_agents"] = new_agents
    return "İşte plan:\n```json\n" + json.dumps(data, ensure_ascii=False) + "\n```"


# ---------------------------------------------------------------------------
# 1. Veri kökü, tohumsuzluk, otomatik orkestratör
# ---------------------------------------------------------------------------


def test_office_creation_spawns_orchestrator_and_skeleton(desk, vault):
    assert desk.list() == []  # tohum yok

    office = desk.create(DeskOffice(name="medya", purpose="Medya işleri", charter="Tüzük."))
    base = vault / "Entropy" / "Desk" / "Offices" / "medya"
    assert (base / "OFFICE.md").is_file()
    for folder in ("agents", "projects", "reports", "inbox", "memory"):
        assert (base / folder).is_dir()

    orchestrator = desk.agents("medya").get(ORCHESTRATOR_AGENT)
    assert orchestrator is not None
    assert (base / "agents" / ORCHESTRATOR_AGENT / "AGENT.md").is_file()
    assert orchestrator.office_role == "orchestrator"
    assert office.orchestrator == ORCHESTRATOR_AGENT
    # Orkestratör üye (alt ajan) değildir: planlar, üretmez.
    assert desk.get("medya").members == []


def test_desk_does_not_see_entropy_agents(desk, vault):
    """Kural 1: Desk, Entropy'nin `Entropy/Agents` kadrosunu kullanmaz."""
    entropy_registry = AgentRegistry(vault_path=vault)
    entropy_registry.create(AgentSpec(name="entropy-ozel", description="Entropy ajanı"))

    desk.create(DeskOffice(name="medya", purpose="Medya"))
    names = [a.name for a in desk.agents("medya").list()]
    assert names == [ORCHESTRATOR_AGENT]
    assert "entropy-ozel" not in names
    assert desk.get("medya").members == []

    from entropy.agents.desk_registry import DeskAgentsView

    assert [s.name for s in DeskAgentsView(desk).list()] == [ORCHESTRATOR_AGENT]


def test_office_agents_are_compiled_into_office_workdir(desk, tmp_path):
    """Kural 8: derleme ofisin `workdir`ine; yoksa ofis klasörüne."""
    project = tmp_path / "kullanici-projesi"
    project.mkdir()
    desk.create(DeskOffice(name="medya", purpose="Medya", workdir=str(project)))

    assert (project / ".agents" / "agents" / ORCHESTRATOR_AGENT / "agent.md").is_file()
    assert (project / ".claude" / "agents" / f"{ORCHESTRATOR_AGENT}.md").is_file()

    # workdir'siz ofis kendi klasörüne derlenir.
    desk.create(DeskOffice(name="yerel", purpose="Yerel"))
    office_dir = desk.office_dir("yerel")
    assert (office_dir / ".agents" / "agents" / ORCHESTRATOR_AGENT / "agent.md").is_file()


# ---------------------------------------------------------------------------
# 2. Orkestratör sözleşmesi: araç kısıtı + "Entropy" dizgesi yok
# ---------------------------------------------------------------------------


def test_orchestrator_compilation_is_read_only_and_forbids_writing(desk):
    desk.create(DeskOffice(name="medya", purpose="Medya"))
    spec = desk.agents("medya").get(ORCHESTRATOR_AGENT)

    claude = render_claude_agent(spec)
    assert "tools: Read, Glob, Grep, WebFetch, WebSearch" in claude
    for banned in ("Write", "Edit", "Bash"):
        assert f" {banned}," not in claude.split("\n---")[0]
    assert "Kod yazma" in claude

    agy = render_agy_agent(spec)
    assert "rules:" in agy
    assert "Kod yazma" in agy
    assert "Kabuk komutu" in agy


def test_orchestrator_frontmatter_survives_yaml_parsing(desk):
    """
    Yasak kuralları YAML'dan sağlam çıkmalı.

    `render_frontmatter` listeyi akış dizisi (`[a, b]`) olarak yazıyor: virgül
    içeren bir kural üç ayrı kurala bölünüyor, ": " içeren kural eşleme
    sanılıyordu — yani yazma yasağı sessizce bozuluyordu.
    """
    yaml = pytest.importorskip("yaml")
    desk.create(DeskOffice(name="medya", purpose="Medya"))
    spec = desk.agents("medya").get(ORCHESTRATOR_AGENT)

    front = yaml.safe_load(render_agy_agent(spec).split("---")[1])
    rules = front["rules"]
    assert all(isinstance(r, str) for r in rules)
    assert any("Kod yazmak" in r and "yasak" in r for r in rules)
    assert any("Kabuk komutu" in r for r in rules)
    assert isinstance(front["description"], str)


def test_orchestrator_tools_stay_read_only_even_if_policy_says_otherwise(desk):
    """Politika alanı elle gevşetilse bile orkestratör yazma aracı almaz."""
    desk.create(DeskOffice(name="medya", purpose="Medya"))
    agents = desk.agents("medya")
    spec = agents.get(ORCHESTRATOR_AGENT)
    from dataclasses import replace

    agents.update(replace(spec, tools_policy="full"))
    claude = render_claude_agent(agents.get(ORCHESTRATOR_AGENT))
    assert "tools: Read, Glob, Grep, WebFetch, WebSearch" in claude


def test_compiled_office_agents_never_mention_entropy(desk, board, vault):
    """
    Kural 5: derlenmiş dosyalar ve plan/eval prompt'ları "Entropy" içermez.

    Ofis tüzüğü kullanıcı metni olduğu için hariç tutulur; bu testte tüzüğe
    bilerek "Entropy" yazılmaz.
    """
    desk.create(DeskOffice(name="medya", purpose="Medya işleri", charter="Kaynaklı yaz."))
    agents = desk.agents("medya")
    agents.update(AgentSpec(name="yazar", role="worker", description="Yazar",
                            provider="agy", tools_policy="read-write",
                            prompt="Metin yazarsın."))

    for spec in agents.list():
        assert "Entropy" not in render_agy_agent(spec)
        assert "Entropy" not in render_claude_agent(spec)
        assert "Entropy" not in spec.path.read_text(encoding="utf-8")

    office = desk.get("medya")
    card = board.create(TaskCard(id=new_task_id("Kart"), title="Kart", goal="Hedef",
                                 office="medya"))
    harness = OfficeHarness("medya", board=board, offices=desk)
    plan_prompt = harness.build_plan_prompt(office, card)
    assert "Entropy" not in plan_prompt
    eval_prompt = harness.build_eval_prompt(office, card, [card])
    assert "Entropy" not in eval_prompt


# ---------------------------------------------------------------------------
# 3. Orkestratör kendi alt ajanlarını oluşturur
# ---------------------------------------------------------------------------


def test_plan_new_agents_are_written_and_compiled(desk, board, tmp_path):
    workdir = tmp_path / "proje"
    workdir.mkdir()
    desk.create(DeskOffice(name="medya", purpose="Medya", workdir=str(workdir)))

    bridge = _ScriptedBridge([
        ("office-plan", _plan(
            [{"title": "Metni yaz", "goal": "Taslak", "criteria": ["kaynaklı"],
              "agent": "metin-yazari"}],
            new_agents=[{"name": "metin-yazari", "role": "worker",
                         "description": "Reklam metni yazar",
                         "provider": "agy", "tools_policy": "read-write",
                         "prompt": "Kısa ve kanıtlı metin yazarsın."}],
        ), True),
        ("card-", "# Taslak\nBitti.", True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    card = board.create(TaskCard(id=new_task_id("İş"), title="İş", goal="Hedef",
                                 office="medya"))
    harness = OfficeHarness("medya", board=board, offices=desk,
                            bridge_factory=lambda p: bridge)
    assert harness.start(card.id) is True

    created = desk.agents("medya").get("metin-yazari")
    assert created is not None
    assert created.tools_policy == "read-write"
    # Alt ajan yazma araçlarıyla derlenir (orkestratörden farkı burada).
    assert "Write" in render_claude_agent(created)
    assert (workdir / ".agents" / "agents" / "metin-yazari" / "agent.md").is_file()
    # Kadroya girdiği için görev ona atandı (ilk üyeye düşürülmedi).
    child = board.get(board.get(card.id).children[0])
    assert child.agent == "metin-yazari"


def test_plan_new_agents_cannot_overwrite_or_clone_orchestrator(desk, board):
    desk.create(DeskOffice(name="medya", purpose="Medya"))
    agents = desk.agents("medya")
    agents.update(AgentSpec(name="yazar", role="worker", description="elde var",
                            provider="agy", prompt="Özgün istem."))

    bridge = _ScriptedBridge([
        ("office-plan", _plan(
            [{"title": "İş", "goal": "Hedef", "criteria": [], "agent": "yazar"}],
            new_agents=[
                {"name": "yazar", "description": "EZİLMEMELİ", "prompt": "yeni"},
                {"name": "ikinci-sef", "role": "orchestrator", "description": "kopya"},
            ],
        ), True),
        ("card-", "bitti", True),
        ("office-eval", '```json\n{"grades": []}\n```', True),
    ])
    card = board.create(TaskCard(id=new_task_id("İş"), title="İş", office="medya"))
    OfficeHarness("medya", board=board, offices=desk,
                  bridge_factory=lambda p: bridge).start(card.id)

    assert agents.get("yazar").description == "elde var"
    assert agents.get("ikinci-sef").office_role == "worker"


# ---------------------------------------------------------------------------
# 4. Uçtan uca: proje + kartlar + rapor
# ---------------------------------------------------------------------------


def test_end_to_end_office_project_chain_reports_to_entropy_inbox(desk, board, vault):
    desk.create(DeskOffice(name="medya", purpose="Medya", charter="Kaynaklı yaz."))
    desk.agents("medya").update(AgentSpec(name="yazar", role="worker",
                                          description="Yazar", provider="agy"))
    project = desk.create_project("medya", DeskProject(
        name="kampanya", goal="Yaz kampanyası", charter="Bütçe 10k."))
    assert project.path.is_file()
    assert [p.name for p in desk.list_projects("medya")] == ["kampanya"]

    bridge = _ScriptedBridge([
        ("office-plan", _plan([
            {"title": "Slogan", "goal": "Üç slogan", "criteria": ["Türkçe"],
             "agent": "yazar"},
        ]), True),
        ("card-", "# Slogan\nÜç slogan hazır.", True),
        ("office-eval", '```json\n{"grades": [{"id": "%s", "grade": 0.9, '
                        '"verdict": "iyi"}]}\n```', True),
    ])
    card = board.create(TaskCard(id=new_task_id("Kampanya"), title="Kampanya",
                                 goal="Kampanya kur", office="medya",
                                 project="kampanya"))
    harness = OfficeHarness("medya", board=board, offices=desk,
                            bridge_factory=lambda p: bridge)
    assert harness.start(card.id) is True

    parent = board.get(card.id)
    assert parent.status == "review"
    child = board.get(parent.children[0])
    assert child.agent == "yazar"
    assert child.project == "kampanya"          # proje alt karta miras kalır
    assert "Üç slogan hazır" in parent.summary

    # Planlama prompt'unda projenin tüzüğü var ve çağrı ofis dizininde koştu.
    plan_call = next(c for c in bridge.calls if c["task_id"].startswith("office-plan"))
    assert "kampanya" in plan_call["prompt"] and "Bütçe 10k" in plan_call["prompt"]
    assert plan_call["project_path"] == str(desk.office_dir("medya"))

    # Rapor ofisin kendi klasöründe ve Entropy'nin gelen kutusunda.
    assert (desk.reports_dir("medya") / f"{card.id}.md").is_file()
    from entropy.agents.mailbox import entropy_mailbox

    reports = [m for m in entropy_mailbox(vault_path=vault).list() if m.kind == "report"]
    assert reports and "Kampanya" in reports[-1].text


def test_office_mailbox_lives_under_desk_root(desk, vault):
    desk.create(DeskOffice(name="medya", purpose="Medya"))
    from entropy.agents.mailbox import ask_office, office_mailbox

    ask_office("medya", "bütçe ne?", vault_path=vault)
    box = office_mailbox("medya", vault_path=vault)
    assert box.inbox_dir == vault / DESK_SUBDIR / "medya" / "inbox"
    assert box.unread_count() == 1


# ---------------------------------------------------------------------------
# 5. Manifest: Entropy tüm orkestratörleri bilir
# ---------------------------------------------------------------------------


def test_manifest_lists_offices_with_orchestrators_and_rules(desk):
    desk.create(DeskOffice(name="medya", purpose="Medya işleri"))
    desk.create(DeskOffice(name="hukuk", purpose="Sözleşme incelemesi"))

    text = desk_manifest(desk)
    assert "medya" in text and "hukuk" in text
    assert ORCHESTRATOR_AGENT in text
    assert "/desk task" in text and "/ask" in text
    assert len(text) < 700

    roster = desk_roster(desk)
    assert {r["office"] for r in roster} == {"medya", "hukuk"}
    assert all(r["orchestrator"] == ORCHESTRATOR_AGENT for r in roster)


def test_manifest_prefers_memory_layer_roster(desk, monkeypatch):
    """Kural 6: roster bellek ajanının `desk_roster()`ından gelir (varsa)."""
    import sys
    import types

    module = types.ModuleType("entropy.memory.office_graph")
    module.desk_roster = lambda: [
        {"office": "graf-ofisi", "orchestrator": "orkestrator", "purpose": "graftan"}
    ]
    monkeypatch.setitem(sys.modules, "entropy.memory.office_graph", module)
    desk.create(DeskOffice(name="medya", purpose="Medya"))

    text = desk_manifest()
    assert "graf-ofisi" in text


def test_manifest_empty_without_offices(desk):
    assert desk_manifest(desk) == ""


# ---------------------------------------------------------------------------
# 6. Komutlar
# ---------------------------------------------------------------------------


def test_desk_office_agent_and_project_commands(vault):
    from entropy.core.slash_commands import try_handle_local_command

    def run(text):
        return try_handle_local_command(text, bridge=None)

    out = run("/desk office add medya :: Medya işleri")
    assert "medya" in out and ORCHESTRATOR_AGENT in out

    desk = DeskRegistry(vault_path=vault)
    assert desk.get("medya") is not None
    assert desk.agents("medya").get(ORCHESTRATOR_AGENT) is not None

    out = run("/desk agent add medya kurgucu :: Video kurgular")
    assert "kurgucu" in out
    assert desk.agents("medya").get("kurgucu").description == "Video kurgular"

    out = run("/desk agent edit medya kurgucu :: Yeni açıklama")
    assert desk.agents("medya").get("kurgucu").description == "Yeni açıklama"

    out = run(f"/desk agent rm medya {ORCHESTRATOR_AGENT}")
    assert "silinemez" in out
    assert desk.agents("medya").get(ORCHESTRATOR_AGENT) is not None

    out = run("/desk project add medya kampanya :: Yaz kampanyası")
    assert "kampanya" in out
    assert desk.get_project("medya", "kampanya").goal == "Yaz kampanyası"

    out = run("/desk agent rm medya kurgucu")
    assert "silindi" in out
    assert desk.agents("medya").get("kurgucu") is None

    out = run("/desk office rm medya")
    assert "silindi" in out
    assert desk.get("medya") is None


def test_desk_task_command_binds_project(vault, monkeypatch):
    from entropy.core import slash_commands

    desk = DeskRegistry(vault_path=vault)
    desk.create(DeskOffice(name="medya", purpose="Medya"))
    desk.create_project("medya", DeskProject(name="kampanya", goal="Yaz"))

    started = {}
    monkeypatch.setattr(
        slash_commands.__dict__.get("OfficeHarness", OfficeHarness), "start",
        lambda self, card_id: started.setdefault("card", card_id) or True,
        raising=False,
    )
    out = slash_commands.try_handle_local_command(
        "/desk task medya @kampanya Kampanya kur :: Üç slogan", bridge=None
    )
    assert "medya" in out
    card = TaskBoard(vault_path=vault).get(started["card"])
    assert card.project == "kampanya"
    assert card.office == "medya"
