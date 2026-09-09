"""
FAZ 9 — Desk ↔ Entropy yön ve veri ayrımı, sağlayıcı nötrleştirme.

Kapsam:
- B-9.2 kart deposu ayrımı ve eski kasadan taşıma
- B-9.3 `/desk msg` → `instruct_office` → plan prompt'unda `[TALİMAT]`
- B-9.4 yön kilidi (Entropy kutusu yalnızca report/status)
- B-9.5 sağlayıcı nötrleştirme (`config.provider`)
- Ek-1 kadro karışmaması, Ek-2 eski tohum işareti

Hiçbir test gerçek agy/claude süreci başlatmaz; köprü yerine sözleşmenin
alt kümesini uygulayan bir sahte köprü kullanılır.
"""

import pytest

from entropy.agents.desk_registry import (
    DeskOffice,
    DeskRegistry,
    is_seed_leftover,
)
from entropy.agents.harness import OfficeHarness
from entropy.agents.mailbox import (
    ENTROPY_OWNER,
    MailboxScopeError,
    Message,
    emit_terminal,
    entropy_mailbox,
    instruct_office,
    office_mailbox,
    office_status,
    report_to_entropy,
    text_part,
)
from entropy.agents.registry import AgentRegistry, AgentSpec, default_provider
from entropy.agents.tasks import (
    ALL_CARDS,
    MIGRATION_LOG_SUBPATH,
    TASKS_SUBDIR,
    TaskBoard,
    TaskCard,
    new_task_id,
)


# ---------------------------------------------------------------------------
# Düzenek
# ---------------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture(autouse=True)
def isolated_vault(vault, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", vault, raising=False)
    return vault


@pytest.fixture(autouse=True)
def clean_board_migration_cache():
    TaskBoard._migrated_vaults.clear()
    DeskRegistry._policy_migrated_vaults.clear()
    OfficeHarness._active.clear()
    yield
    TaskBoard._migrated_vaults.clear()
    DeskRegistry._policy_migrated_vaults.clear()
    OfficeHarness._active.clear()


@pytest.fixture
def offices(vault):
    reg = DeskRegistry(vault_path=vault)
    reg.create(DeskOffice(name="alfa-ofisi", purpose="Planlar.", charter="Kabul: kısa."))
    reg.agents("alfa-ofisi").update(
        AgentSpec(name="isci", description="işi yapar", provider="agy")
    )
    return reg


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


class ScriptedBridge:
    """Sırayla hazır yanıt döndüren köprü (gerçek köprünün sözleşme altkümesi)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.current_conversation_id = None

    def send_background_task_async(self, task_id, task_name, prompt, mode="accept-edits",
                                   on_result=None, save_report=True, agent=None,
                                   needs_write=None, conversation_id=None, **_):
        self.calls.append({"task_id": task_id, "prompt": prompt, "agent": agent})
        text = self.responses.pop(0) if self.responses else ""
        if on_result is not None:
            on_result(text, True)

    def terminate_background_task(self, task_id):
        return True


# ---------------------------------------------------------------------------
# B-9.2 — kart deposu ayrımı
# ---------------------------------------------------------------------------


def test_office_card_is_written_under_office_vault(board, offices, vault):
    card = board.create(TaskCard(id=new_task_id("Ofis"), title="Ofis kartı",
                                 office="alfa-ofisi", agent="isci"))
    expected = vault / "Desk/Offices/alfa-ofisi/cards" / f"{card.id}.md"
    assert expected.is_file()
    assert not (vault / TASKS_SUBDIR / f"{card.id}.md").exists()
    # Kimlikten okuma iki kökü de bilir.
    assert board.get(card.id) is not None
    assert board.get(card.id).office == "alfa-ofisi"


def test_entropy_card_stays_in_entropy_tasks(board, vault):
    card = board.create(TaskCard(id=new_task_id("Kendi"), title="Kendi kartım"))
    assert (vault / TASKS_SUBDIR / f"{card.id}.md").is_file()


def test_list_scopes_are_disjoint(board, offices):
    own = board.create(TaskCard(id=new_task_id("Kendi"), title="Kendi"))
    office_card = board.create(TaskCard(id=new_task_id("Ofis"), title="Ofis",
                                        office="alfa-ofisi"))
    assert [c.id for c in board.list()] == [own.id]
    assert [c.id for c in board.list(office="alfa-ofisi")] == [office_card.id]
    assert {c.id for c in board.list(office=ALL_CARDS)} == {own.id, office_card.id}


def test_legacy_office_cards_migrate_once_and_are_logged(vault, offices):
    """Karma kasa: eski konumdaki ofis kartı taşınır, Entropy kartı yerinde kalır."""
    legacy_dir = vault / TASKS_SUBDIR
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "eski-ofis-karti.md").write_text(
        "---\nid: eski-ofis-karti\ntitle: Eski\nstatus: backlog\n"
        "office: alfa-ofisi\n---\n\n## Hedef\nhedef\n",
        encoding="utf-8",
    )
    (legacy_dir / "eski-entropy-karti.md").write_text(
        "---\nid: eski-entropy-karti\ntitle: Benim\nstatus: backlog\noffice:\n---\n\n"
        "## Hedef\nhedef\n",
        encoding="utf-8",
    )

    board = TaskBoard(vault_path=vault)  # __init__ taşımayı tetikler

    moved = vault / "Desk/Offices/alfa-ofisi/cards/eski-ofis-karti.md"
    assert moved.is_file()
    assert not (legacy_dir / "eski-ofis-karti.md").exists()
    assert (legacy_dir / "eski-entropy-karti.md").is_file()

    log = (vault / MIGRATION_LOG_SUBPATH).read_text(encoding="utf-8")
    assert "eski-ofis-karti" in log and "taşındı" in log

    # `list()` ofis kartı içermez; ofis kapsamı yalnızca ofis kartını verir.
    assert [c.id for c in board.list()] == ["eski-entropy-karti"]
    assert [c.id for c in board.list(office="alfa-ofisi")] == ["eski-ofis-karti"]

    # İkinci koşu idempotent: yeni taşıma yok, dosya çoğalmıyor.
    TaskBoard._migrated_vaults.clear()
    assert TaskBoard(vault_path=vault).migrate_office_cards() == []
    assert len(list((vault / "Desk/Offices/alfa-ofisi/cards").glob("*.md"))) == 1


def test_office_status_and_stop_read_new_root(vault, offices, board):
    card = board.create(TaskCard(id=new_task_id("Ust"), title="Üst", office="alfa-ofisi",
                                 agent="orkestrator", status="running"))
    info = office_status("alfa-ofisi", vault_path=vault)
    assert info["exists"] is True
    assert [r["id"] for r in info["running"]] == [card.id]


def test_resume_all_finds_office_cards_in_new_root(vault, offices, board):
    card = board.create(TaskCard(id=new_task_id("Ust"), title="Üst", office="alfa-ofisi",
                                 agent="orkestrator", status="running",
                                 children=["yok-1"]))
    resumed = OfficeHarness.resume_all(
        board=board, offices=offices, bridge_factory=lambda p: ScriptedBridge([])
    )
    assert card.id in resumed


# ---------------------------------------------------------------------------
# B-9.3 — Entropy → ofis talimatı
# ---------------------------------------------------------------------------


def test_desk_msg_command_writes_instruction(vault, offices):
    from entropy.core.slash_commands import try_handle_local_command

    out = try_handle_local_command("/desk msg alfa-ofisi :: önce testleri koş", bridge=None)
    assert "Talimat" in out
    msgs = office_mailbox("alfa-ofisi", vault_path=vault).list()
    assert [m.kind for m in msgs] == ["instruction"]
    assert msgs[0].text == "önce testleri koş"
    assert msgs[0].from_ == ENTROPY_OWNER


def test_desk_msg_rejects_unknown_office_and_empty_text(vault, offices):
    from entropy.core.slash_commands import try_handle_local_command

    assert "ofis yok" in try_handle_local_command("/desk msg yok-ofis :: bir şey", bridge=None)
    assert "Kullanım" in try_handle_local_command("/desk msg alfa-ofisi ::", bridge=None)


def test_plan_prompt_has_instruction_section_and_marks_read(vault, offices, board):
    instruct_office("alfa-ofisi", "yalnızca 2026 kaynaklarını kullan", vault_path=vault)
    card = board.create(TaskCard(id=new_task_id("Kart"), title="Kart", goal="hedef",
                                 office="alfa-ofisi"))
    harness = OfficeHarness("alfa-ofisi", board=board, offices=offices)
    prompt = harness.build_plan_prompt(harness.office, card)
    assert "[TALİMAT" in prompt
    assert "yalnızca 2026 kaynaklarını kullan" in prompt
    # Okundu işaretlendi: ikinci planlamada aynı yön tekrar enjekte edilmez.
    assert office_mailbox("alfa-ofisi", vault_path=vault).unread_count() == 0
    assert "yalnızca 2026" not in harness.build_plan_prompt(harness.office, card)


# ---------------------------------------------------------------------------
# B-9.4 — yön kilidi
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["instruction", "question"])
def test_entropy_inbox_rejects_downward_kinds(vault, kind):
    box = entropy_mailbox(vault_path=vault)
    with pytest.raises(MailboxScopeError):
        box.send(Message(from_="alfa-ofisi", to=ENTROPY_OWNER, role="agent",
                         kind=kind, parts=[text_part("emir")], status="submitted"))


def test_report_and_terminal_paths_still_work(vault, offices):
    report_to_entropy("alfa-ofisi", "Rapor", "gövde", task_id="card-1", vault_path=vault)
    emit_terminal("card-1", "alfa-ofisi", "completed", summary="bitti", vault_path=vault)
    kinds = sorted(m.kind for m in entropy_mailbox(vault_path=vault).list())
    assert kinds == ["report", "status"]


def test_instruct_office_still_allowed_downward(vault, offices):
    msg = instruct_office("alfa-ofisi", "kapsamı daralt", vault_path=vault)
    assert msg.kind == "instruction"


# ---------------------------------------------------------------------------
# B-9.5 — sağlayıcı nötrleştirme
# ---------------------------------------------------------------------------


@pytest.fixture
def claude_only(monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "provider", "claude", raising=False)
    if hasattr(config, "default_provider"):
        monkeypatch.setattr(config, "default_provider", lambda: "claude", raising=False)
    return config


def test_default_provider_follows_config(claude_only):
    assert default_provider() == "claude"
    assert AgentSpec(name="x").provider == "claude"
    assert TaskCard(id="x").provider == "claude"


def test_new_office_and_orchestrator_use_config_provider(vault, claude_only):
    desk = DeskRegistry(vault_path=vault)
    office = desk.create(DeskOffice(name="claude-ofisi", purpose="test"))
    assert office.default_provider == "claude"
    orchestrator = desk.agents("claude-ofisi").get(office.orchestrator)
    assert orchestrator.provider == "claude"
    member = desk.create_member("claude-ofisi", "isci", description="işçi")
    assert member.provider == "claude"


def test_plan_schema_example_follows_roster_provider(vault, claude_only, board):
    desk = DeskRegistry(vault_path=vault)
    desk.create(DeskOffice(name="claude-ofisi", purpose="test"))
    desk.create_member("claude-ofisi", "isci", description="işçi")
    card = board.create(TaskCard(id=new_task_id("Kart"), title="Kart", office="claude-ofisi"))
    harness = OfficeHarness("claude-ofisi", board=board, offices=desk)
    prompt = harness.build_plan_prompt(harness.office, card)
    assert '"provider": "claude"' in prompt
    assert '"provider": "agy"' not in prompt


def test_office_chain_closes_without_agy(vault, claude_only, board):
    """Uçtan uca ofis zinciri: sahte köprü, agy hiç çağrılmadan kapanır."""
    desk = DeskRegistry(vault_path=vault)
    desk.create(DeskOffice(name="claude-ofisi", purpose="test"))
    desk.create_member("claude-ofisi", "isci", description="işçi")
    card = board.create(TaskCard(id=new_task_id("Kart"), title="Kart", goal="hedef",
                                 office="claude-ofisi", agent="orkestrator"))

    seen_providers = []
    plan = (
        '```json\n{"subtasks": [{"title": "Alt", "goal": "alt hedef", '
        '"criteria": ["ölçüt"], "agent": "isci", "provider": "", "model": ""}]}\n```'
    )
    bridge = ScriptedBridge([plan, "Alt kart çıktısı.",
                             '```json\n{"grades": [], "verdict": "yeterli"}\n```'])

    def factory(provider):
        seen_providers.append(provider)
        return bridge

    harness = OfficeHarness("claude-ofisi", board=board, offices=desk, bridge_factory=factory)
    harness.start(card.id)

    assert seen_providers, "köprü hiç istenmedi"
    assert "agy" not in seen_providers
    children = board.list(office="claude-ofisi")
    assert any(c.parent == card.id and c.provider == "claude" for c in children)


# ---------------------------------------------------------------------------
# Ek-1 — kadrolar karışmasın
# ---------------------------------------------------------------------------


def test_entropy_registry_never_lists_desk_agents(vault, offices):
    registry = AgentRegistry(vault_path=vault)
    registry.create(AgentSpec(name="yazar", description="Entropy ajanı"))
    names = [s.name for s in registry.list()]
    assert names == ["yazar"]
    assert "orkestrator" not in names  # ofisin orkestratörü Desk kasasında
    assert registry.get("isci") is None


def test_entropy_card_with_office_agent_fails_without_running(vault, offices, board):
    registry = AgentRegistry(vault_path=vault)
    registry.create(AgentSpec(name="yazar", description="Entropy ajanı"))
    card = board.create(TaskCard(id=new_task_id("Kart"), title="Kart", agent="orkestrator"))
    calls = []
    assert board.run(card.id, bridge_factory=lambda p: calls.append(p)) is None
    assert calls == []
    final = board.get(card.id)
    assert final.status == "failed"
    assert "Entropy kadrosunda değil" in final.summary


# ---------------------------------------------------------------------------
# Ek-2 — eski tohum işareti
# ---------------------------------------------------------------------------


def test_seed_leftover_detection(vault):
    desk = DeskRegistry(vault_path=vault)
    desk.create(DeskOffice(name="arastirma-ofisi", purpose="kullanıcının açtığı ofis"))
    desk.create(DeskOffice(name="kullanicinin-ofisi", purpose="kullanıcı açtı"))
    # Ad tabanlı sezgi KALDIRILDI: kullanıcı "arastirma-ofisi" adında gerçek bir
    # ofis açtı ve `/desk` onu "eski tohum" diye işaretliyordu.
    assert is_seed_leftover("arastirma-ofisi", desk) is False
    assert is_seed_leftover("kullanicinin-ofisi", desk) is False

    # Tek ölçüt `seed: true` ön bilgisi.
    path = desk.office_file("kullanicinin-ofisi")
    text = path.read_text(encoding="utf-8").replace("---\n", "---\nseed: true\n", 1)
    path.write_text(text, encoding="utf-8")
    assert is_seed_leftover("kullanicinin-ofisi", desk) is True


def test_desk_listing_marks_seed_leftover(vault):
    from entropy.core.slash_commands import try_handle_local_command

    desk = DeskRegistry(vault_path=vault)
    desk.create(DeskOffice(name="tohum-ofis", purpose="eski tohum"))
    desk.create(DeskOffice(name="arastirma-ofisi", purpose="kullanıcının ofisi"))
    path = desk.office_file("tohum-ofis")
    path.write_text(
        path.read_text(encoding="utf-8").replace("---\n", "---\nseed: true\n", 1),
        encoding="utf-8",
    )
    out = try_handle_local_command("/desk", bridge=None)
    assert "eski tohum" in out
    # İşaret YALNIZCA `seed: true` olan ofise düşer; kullanıcının ofisi temiz.
    user_line = [ln for ln in out.split("🏢") if "arastirma-ofisi" in ln]
    assert user_line and "eski tohum" not in user_line[0]
    # İşaret yalnızca uyarıdır: ofis silinmez.
    assert desk.get("tohum-ofis") is not None


# ---------------------------------------------------------------------------
# Faz 9 (agy-4) — canlı ofisle uyum: politika, model metni, kart devri
# ---------------------------------------------------------------------------


def test_orchestrator_tools_policy_is_normalized_on_load(vault):
    """Kasadaki `tools_policy: full` orkestratör, defter yüklenirken salt okunur olur."""
    desk = DeskRegistry(vault_path=vault)
    desk.create(DeskOffice(name="Arastirma Ofisi", purpose="araştırır",
                           orchestrator="Alfa", default_provider="claude"))
    agents = desk.agents("Arastirma Ofisi")
    agents.update(AgentSpec(name="Alfa", role="orchestrator", description="planlar",
                            provider="claude", model="claude-opus-5",
                            tools_policy="full", office="Arastirma Ofisi"))
    assert agents.get("Alfa").tools_policy == "full"

    # Kasa anahtarı önbellekte olduğu için __init__ geçişi atlar; açıkça çağır.
    changed = DeskRegistry(vault_path=vault).migrate_orchestrator_policies()

    assert changed == ["Arastirma Ofisi/Alfa"]
    assert agents.get("Alfa").tools_policy == "read-only"
    # Derlenmiş kopyalar yeniden üretildi ve yazma araçları düştü.
    claude_file = desk.workdir("Arastirma Ofisi") / ".claude" / "agents" / "Alfa.md"
    assert claude_file.is_file()
    assert "Write" not in claude_file.read_text(encoding="utf-8")
    agy_file = desk.workdir("Arastirma Ofisi") / ".agents" / "agents" / "Alfa" / "agent.md"
    assert agy_file.is_file()

    log = (vault / "Desk/_migrations.log").read_text(encoding="utf-8")
    assert "orkestratör-politika" in log and "read-only" in log

    # İdempotent: ikinci koşuda değişiklik ve yeni günlük satırı yok.
    before = log
    assert DeskRegistry(vault_path=vault).migrate_orchestrator_policies() == []
    assert (vault / "Desk/_migrations.log").read_text(encoding="utf-8") == before


def test_normalize_model_text_rules():
    from entropy.agents.compile import (
        AGY_FALLBACK_MODEL,
        normalize_model_text,
    )

    assert normalize_model_text("fable 5.1 high effort", "claude") == ("fable", "high")
    assert normalize_model_text("Opus", "claude")[0] == "claude-opus-5"
    assert normalize_model_text("sonnet 5", "claude")[0] == "claude-sonnet-5"
    assert normalize_model_text("haiku", "claude")[0] == "claude-haiku-4-5-20251001"
    # Tam kimlik olduğu gibi kabul edilir.
    assert normalize_model_text("claude-fable-5-1", "claude")[0] == "claude-fable-5-1"
    # agy ipuçları.
    assert normalize_model_text("gemini flash", "agy")[0] == "gemini-3.8-flash-high"
    assert normalize_model_text("gemini 3.1 pro low", "agy") == ("gemini-3.1-pro-high", "low")
    # Geçersiz agy metni sağlayıcı varsayılanına düşer.
    assert normalize_model_text("her neyse", "agy")[0] == AGY_FALLBACK_MODEL


def test_office_default_model_is_normalized_and_effort_extracted(vault):
    desk = DeskRegistry(vault_path=vault)
    desk.create(DeskOffice(name="ofis", default_provider="claude",
                           default_model="fable 5.1 high effort"))
    office = desk.get("ofis")
    assert office.default_model == "fable"
    assert office.default_effort == "high"
    # Orkestratör ofis eforunu miras alır.
    orch = desk.agents("ofis").get(office.orchestrator)
    assert orch.effort == "high"
    assert orch.model == "fable"


def test_desk_agent_cards_are_claimed_by_their_office(vault):
    """Ofissiz ama ajanı bir ofise ait olan kartlar ofis kasasına devredilir."""
    desk = DeskRegistry(vault_path=vault)
    desk.create(DeskOffice(name="Arastirma", orchestrator="Alfa", default_provider="claude"))
    desk.agents("Arastirma").update(AgentSpec(name="Alfa", role="orchestrator",
                                              provider="claude", office="Arastirma"))
    legacy = vault / TASKS_SUBDIR
    legacy.mkdir(parents=True, exist_ok=True)
    for cid in ("kart-1", "kart-2"):
        (legacy / f"{cid}.md").write_text(
            f"---\nid: {cid}\ntitle: {cid}\nstatus: failed\nagent: Alfa\noffice:\n---\n\n"
            "## Hedef\nhedef\n",
            encoding="utf-8",
        )
    # Entropy'nin kendi kartı ve koşan bir kart dokunulmaz kalır.
    (legacy / "kendi.md").write_text(
        "---\nid: kendi\ntitle: Kendi\nstatus: backlog\nagent: distiller\noffice:\n---\n\n"
        "## Hedef\nhedef\n", encoding="utf-8")
    (legacy / "kosan.md").write_text(
        "---\nid: kosan\ntitle: Koşan\nstatus: running\nagent: Alfa\noffice:\n---\n\n"
        "## Hedef\nhedef\n", encoding="utf-8")

    TaskBoard._migrated_vaults.clear()
    board = TaskBoard(vault_path=vault)

    cards_dir = vault / "Desk/Offices/Arastirma/cards"
    assert sorted(p.name for p in cards_dir.glob("*.md")) == ["kart-1.md", "kart-2.md"]
    assert not (legacy / "kart-1.md").exists()
    assert (legacy / "kendi.md").is_file()
    assert (legacy / "kosan.md").is_file()
    assert board.get("kart-1").office == "Arastirma"

    log = (vault / MIGRATION_LOG_SUBPATH).read_text(encoding="utf-8")
    assert "ofise-atandı" in log and "kart-1" in log

    # İdempotent.
    TaskBoard._migrated_vaults.clear()
    assert TaskBoard(vault_path=vault).migrate_office_cards() == []
