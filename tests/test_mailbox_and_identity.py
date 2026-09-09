"""
FAZ 5.3 + 5.4 — posta kutusu, terminal sözleşmesi, kimlik katmanı, agentic sohbet.

Hiçbir test gerçek agy/claude süreci başlatmaz ve hiçbir model çağrılmaz.
Sağlayıcı probları `runner` enjeksiyonuyla, köprü yolları ya küçük bir sahte
köprüyle ya da `subprocess.Popen` taklidiyle sürülen GERÇEK köprüyle sınanır —
sahte köprü imza uyumsuzluklarını gizliyordu (bkz. test_distill_command.py).
"""

import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from entropy.agents.harness import OfficeHarness
from entropy.agents.mailbox import (
    ENTROPY_OWNER,
    MailboxScopeError,
    Mailbox,
    Message,
    agent_mailbox,
    ask_office,
    emit_terminal,
    entropy_mailbox,
    has_terminal_event,
    instructions_section,
    office_mailbox,
    office_status,
    pending_instructions,
    text_part,
)
from entropy.agents.offices import OfficeRegistry, OfficeSpec
from entropy.agents.registry import AgentRegistry, AgentSpec
from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id
from entropy.core.identity import (
    AgenticChat,
    ConversationMap,
    IdentityLayer,
    ProviderStatus,
    login_guidance,
    probe_agy,
    probe_claude,
)


# ---------------------------------------------------------------------------
# Düzenek
# ---------------------------------------------------------------------------


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture(autouse=True)
def isolated_vault(vault, monkeypatch):
    """Kasa yolu teste özel; kullanıcının gerçek kasası kirlenmesin."""
    from entropy.core.config import config

    monkeypatch.setattr(config, "obsidian_vault_path", vault, raising=False)
    return vault


@pytest.fixture(autouse=True)
def clean_active_registry():
    OfficeHarness._active.clear()
    yield
    OfficeHarness._active.clear()


@pytest.fixture
def offices(vault):
    """
    İki ofis + kendi kadroları.

    Faz 6: üyeler ofis ön bilgisinden değil, ofisin `agents/` klasöründen
    türetiliyor; bu yüzden ajanlar da ofisin kendi defterine yazılır.
    """
    reg = OfficeRegistry(vault_path=vault)
    reg.create(OfficeSpec(
        name="arastirma-ofisi",
        purpose="Araştırır.",
        default_provider="agy",
        charter="Kabul: kaynaklı.",
    ))
    _staff(reg, "arastirma-ofisi", ["arastirmaci", "yazar"], "degerlendirici")
    reg.create(OfficeSpec(
        name="ikinci-ofis",
        purpose="Başka iş.",
        default_provider="agy",
    ))
    _staff(reg, "ikinci-ofis", ["yabanci"], "degerlendirici2")
    return reg


def _staff(reg, office, members, evaluator):
    agents = reg.agents(office)
    for name in members:
        agents.update(AgentSpec(name=name, description=f"{name} ajanı", provider="agy"))
    if evaluator:
        agents.update(AgentSpec(name=evaluator, role="evaluator",
                                description="notlar", provider="agy"))


@pytest.fixture
def agents(vault):
    reg = AgentRegistry(vault_path=vault)
    for name in ("orkestrator", "degerlendirici", "arastirmaci", "yazar",
                 "orkestrator2", "degerlendirici2", "yabanci"):
        reg.create(AgentSpec(name=name, description=f"{name} ajanı", provider="agy"))
    return reg


class ScriptedBridge:
    """Sırayla hazır yanıt döndüren köprü (gerçek köprünün sözleşme altkümesi)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.current_conversation_id = None

    def send_background_task_async(self, task_id, task_name, prompt, mode="accept-edits",
                                   on_result=None, save_report=True, agent=None,
                                   needs_write=None, conversation_id=None, **_):
        self.calls.append({
            "task_id": task_id, "prompt": prompt, "agent": agent,
            "conversation_id": conversation_id, "mode": mode,
        })
        text = self.responses.pop(0) if self.responses else ""
        self.current_conversation_id = "conv-agy-1"
        if on_result is not None:
            on_result(text, True)

    def terminate_background_task(self, task_id):
        return True


# ---------------------------------------------------------------------------
# 5.3 — posta kutusu şeması, atomik yazım, okuma, ack
# ---------------------------------------------------------------------------


def test_message_roundtrip_keeps_a2a_field_names(vault):
    """Disk şemasında alan adı `from`; Python tarafında `from_`."""
    box = office_mailbox("arastirma-ofisi", vault_path=vault)
    msg = box.send(Message(
        task_id="t-1", from_=ENTROPY_OWNER, to="arastirma-ofisi",
        kind="instruction", parts=[text_part("kaynak göster")],
    ))
    raw = json.loads(msg.path.read_text(encoding="utf-8"))
    assert raw["from"] == ENTROPY_OWNER and "from_" not in raw
    assert raw["kind"] == "instruction" and raw["status"] == "submitted"
    assert raw["parts"] == [{"type": "text", "content": "kaynak göster"}]

    back = box.list()
    assert len(back) == 1
    assert back[0].from_ == ENTROPY_OWNER
    assert back[0].text == "kaynak göster"


def test_write_is_atomic_no_partial_json_left_behind(vault, monkeypatch):
    """
    Yazım tmp + os.replace ile: okuyan taraf yarım JSON görmemeli.

    os.replace'in çağrıldığını doğrulamak yetmez; yazım sırasında kutuyu okuyan
    bir iş parçacığı da hiçbir zaman bozuk mesaj görmemeli.
    """
    import os as _os

    box = office_mailbox("arastirma-ofisi", vault_path=vault)
    seen_tmp = []
    real_replace = _os.replace

    def spy_replace(src, dst):
        seen_tmp.append(Path(src).name)
        # Yer değiştirmeden ÖNCE hedef adla bir dosya varsa okunabilir olmalı.
        assert box.list() is not None
        return real_replace(src, dst)

    monkeypatch.setattr("entropy.agents.mailbox.os.replace", spy_replace)
    box.send(Message(from_=ENTROPY_OWNER, to="arastirma-ofisi", parts=[text_part("a")]))
    assert seen_tmp and ".tmp" in seen_tmp[0]
    # Geçici dosya geride kalmamalı.
    assert not list(box.inbox_dir.glob("*.tmp*"))
    assert len(box.list()) == 1


def test_unread_mark_read_and_ack(vault):
    box = office_mailbox("arastirma-ofisi", vault_path=vault)
    m1 = box.send(Message(from_=ENTROPY_OWNER, to="x", parts=[text_part("bir")]))
    m2 = box.send(Message(from_=ENTROPY_OWNER, to="x", parts=[text_part("iki")]))

    assert box.unread_count() == 2
    assert box.mark_read(m1.id) is True
    assert [m.id for m in box.list(unread=True)] == [m2.id]

    assert box.ack(m2.id, status="completed") is True
    got = box.get(m2.id)
    assert got.acked is True and got.read is True and got.status == "completed"
    # Onay silme değildir: mesaj arşivde kalır.
    assert len(box.list()) == 2


def test_invalid_kind_status_and_terminal_are_rejected(vault):
    box = entropy_mailbox(vault_path=vault)
    with pytest.raises(ValueError):
        box.send(Message(kind="gossip", parts=[text_part("x")]))
    with pytest.raises(ValueError):
        box.send(Message(status="pending", parts=[text_part("x")]))
    # terminal=True yalnızca completed/failed/canceled ile anlamlı.
    with pytest.raises(ValueError):
        box.send(Message(kind="status", status="working", terminal=True))


def test_corrupt_message_file_does_not_break_the_box(vault):
    box = entropy_mailbox(vault_path=vault)
    box.send(Message(from_="x", parts=[text_part("saglam")]))
    (box.inbox_dir / "20260101-000000-bozuk.json").write_text("{yarim", encoding="utf-8")
    msgs = box.list()
    assert len(msgs) == 1 and msgs[0].text == "saglam"


def test_peer_to_peer_message_only_within_same_office(vault, offices, agents):
    """Kapsam kuralı: ajan → ajan mesajı yalnızca AYNI ofis içinde."""
    box = agent_mailbox("yazar", vault_path=vault)
    ok = box.send(Message(from_="arastirmaci", to="yazar", parts=[text_part("taslak")]))
    assert ok.path.exists()

    with pytest.raises(MailboxScopeError):
        box.send(Message(from_="yabanci", to="yazar", parts=[text_part("sızıntı")]))
    # Entropy ve ofisin kendisi her zaman yazabilir.
    box.send(Message(from_=ENTROPY_OWNER, to="yazar", parts=[text_part("talimat")]))
    box.send(Message(from_="arastirma-ofisi", to="yazar", parts=[text_part("ofis")]))
    assert len(box.list()) == 3


def test_mailbox_updated_signal_carries_owner(vault, qapp):
    from entropy.core.event_bus import bus

    seen = []
    bus.mailbox_updated.connect(lambda k, n: seen.append((k, n)))
    office_mailbox("arastirma-ofisi", vault_path=vault).send(
        Message(from_=ENTROPY_OWNER, parts=[text_part("x")])
    )
    assert ("office", "arastirma-ofisi") in seen


def test_watcher_reports_only_changes_after_first_scan(vault):
    from entropy.agents.mailbox import MailboxWatcher

    box = office_mailbox("arastirma-ofisi", vault_path=vault)
    box.send(Message(from_=ENTROPY_OWNER, parts=[text_part("ilk")]))

    watcher = MailboxWatcher(vault_path=vault)
    # İlk tarama yalnızca mevcut durumu kaydeder; "yeni mesaj" yaymaz.
    assert watcher.scan() == []
    box.send(Message(from_=ENTROPY_OWNER, parts=[text_part("ikinci")]))
    assert ("office", "arastirma-ofisi") in watcher.scan()


# ---------------------------------------------------------------------------
# 5.3 — /ask akışı ve talimatın plana girmesi
# ---------------------------------------------------------------------------


def test_ask_command_writes_question_to_office_inbox(vault, offices, agents):
    from entropy.core.slash_commands import try_handle_local_command

    out = try_handle_local_command("/ask arastirma-ofisi kaynakları listele", bridge=None)
    assert out is not None and "arastirma-ofisi" in out
    msgs = office_mailbox("arastirma-ofisi", vault_path=vault).list()
    assert len(msgs) == 1
    assert msgs[0].kind == "question" and msgs[0].from_ == ENTROPY_OWNER
    assert msgs[0].text == "kaynakları listele"


def test_ask_command_rejects_unknown_office(vault, offices):
    from entropy.core.slash_commands import try_handle_local_command

    out = try_handle_local_command("/ask yok-boyle-ofis soru", bridge=None)
    assert "adında ofis yok" in out
    assert not (vault / "Entropy/Offices/yok-boyle-ofis").exists()


def test_pending_instructions_marks_read_and_builds_section(vault, offices):
    ask_office("arastirma-ofisi", "önce maliyeti çıkar", vault_path=vault)
    msgs = pending_instructions("arastirma-ofisi", vault_path=vault)
    assert len(msgs) == 1
    section = instructions_section(msgs)
    assert "POSTA KUTUSU" in section and "önce maliyeti çıkar" in section
    # İkinci okuma boş: aynı yön ikinci planlamaya tekrar enjekte edilmemeli.
    assert pending_instructions("arastirma-ofisi", vault_path=vault) == []


def test_plan_prompt_contains_mailbox_instructions(vault, offices, agents):
    board = TaskBoard(vault_path=vault)
    ask_office("arastirma-ofisi", "yalnızca 2026 kaynaklarını kullan", vault_path=vault)
    card = board.create(TaskCard(id=new_task_id("Kart"), title="Kart", goal="hedef",
                                 office="arastirma-ofisi"))
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices)
    prompt = harness.build_plan_prompt(harness.office, card)
    assert "yalnızca 2026 kaynaklarını kullan" in prompt
    assert prompt.index("POSTA KUTUSU") < prompt.index("[ÜST KART]")


# ---------------------------------------------------------------------------
# 5.3 — terminal sözleşmesi
# ---------------------------------------------------------------------------


def test_task_board_emits_terminal_event_on_success_and_failure(vault, agents):
    board = TaskBoard(vault_path=vault)
    ok_card = board.create(TaskCard(id=new_task_id("iyi"), title="iyi", agent="yazar"))
    bad_card = board.create(TaskCard(id=new_task_id("kotu"), title="kotu", agent="yazar"))

    board._finish(ok_card.id, "çıktı", True)
    board._finish(bad_card.id, "hata", False)

    assert has_terminal_event(ok_card.id, vault_path=vault)
    assert has_terminal_event(bad_card.id, vault_path=vault)
    events = {m.task_id: m.status for m in entropy_mailbox(vault_path=vault).list(kind="status")}
    assert events[ok_card.id] == "completed"
    assert events[bad_card.id] == "failed"


def test_task_board_stop_emits_canceled_terminal_event(vault, agents):
    board = TaskBoard(vault_path=vault)
    card = board.create(TaskCard(id=new_task_id("dur"), title="dur", agent="yazar",
                                 status="running"))
    board.stop(card.id)
    msgs = [m for m in entropy_mailbox(vault_path=vault).list(kind="status")
            if m.task_id == card.id]
    assert msgs and msgs[-1].status == "canceled" and msgs[-1].terminal is True


def test_harness_full_chain_ends_with_report_and_terminal_event(vault, offices, agents):
    """
    Uçtan uca: talimat → plan → alt kart → değerlendirme → rapor + terminal olay.

    "Hiçbir yol terminal olaysız bitmez" kuralının asıl testi bu: zincirin
    başarılı çıkışı da terminal olay yaymak zorunda.
    """
    board = TaskBoard(vault_path=vault)
    ask_office("arastirma-ofisi", "kısa tut", vault_path=vault)
    plan = json.dumps({"subtasks": [
        {"title": "Tara", "goal": "kaynak tara", "criteria": ["kaynaklı"],
         "agent": "arastirmaci", "provider": "agy"},
    ]})
    grades = json.dumps({"grades": [{"id": "__CHILD__", "grade": 0.9, "verdict": "iyi"}]})
    bridge = ScriptedBridge([f"```json\n{plan}\n```", "alt görev çıktısı", grades])

    card = board.create(TaskCard(id=new_task_id("Ust"), title="Ust", goal="hedef"))
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda provider: bridge)
    assert harness.start(card.id) is True

    # Planlama prompt'u posta kutusundaki talimatı taşımalı.
    assert "kısa tut" in bridge.calls[0]["prompt"]

    final = board.get(card.id)
    assert final.status == "review"
    assert has_terminal_event(card.id, vault_path=vault), "terminal olay yayılmadı"

    reports = entropy_mailbox(vault_path=vault).list(kind="report")
    assert reports and reports[-1].task_id == card.id
    assert "alt görev çıktısı" in reports[-1].text


def test_harness_failure_and_stop_paths_emit_terminal_events(vault, offices, agents):
    board = TaskBoard(vault_path=vault)
    bad = board.create(TaskCard(id=new_task_id("bozuk"), title="bozuk", goal="h"))
    bridge = ScriptedBridge(["plan değil, düz metin"])
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices,
                            bridge_factory=lambda provider: bridge)
    harness.start(bad.id)
    assert board.get(bad.id).status == "failed"
    fail_events = [m for m in entropy_mailbox(vault_path=vault).list(kind="status")
                   if m.task_id == bad.id]
    assert fail_events and fail_events[-1].status == "failed"

    stopped = board.create(TaskCard(id=new_task_id("kes"), title="kes", goal="h",
                                    office="arastirma-ofisi", status="running"))
    OfficeHarness("arastirma-ofisi", board=board, offices=offices).stop(stopped.id)
    cancel_events = [m for m in entropy_mailbox(vault_path=vault).list(kind="status")
                     if m.task_id == stopped.id]
    assert cancel_events and cancel_events[-1].status == "canceled"


def test_emit_terminal_rejects_non_terminal_status(vault):
    with pytest.raises(ValueError):
        emit_terminal("t-1", "ofis", "working", vault_path=vault)


# ---------------------------------------------------------------------------
# 5.3 — ofis durum panosu
# ---------------------------------------------------------------------------


def test_office_status_reports_running_spend_inbox_and_terminals(vault, offices, agents):
    board = TaskBoard(vault_path=vault)
    card = board.create(TaskCard(id=new_task_id("Pano"), title="Pano", goal="h",
                                 office="arastirma-ofisi", status="running"))
    harness = OfficeHarness("arastirma-ofisi", board=board, offices=offices)
    harness._save_card_state(card.id, phase="running", tokens=1234)
    ask_office("arastirma-ofisi", "bir soru", vault_path=vault)
    emit_terminal(card.id, "arastirma-ofisi", "completed", "bitti", vault_path=vault)

    info = office_status("arastirma-ofisi", vault_path=vault)
    assert info["exists"] is True
    assert info["orchestrator"] == "orkestrator"
    assert sorted(info["members"]) == ["arastirmaci", "yazar"]
    assert info["inbox_unread"] == 1
    assert info["spent_tokens"] == 1234
    assert [r["id"] for r in info["running"]] == [card.id]
    assert info["running"][0]["tokens"] == 1234
    assert info["recent_terminal"] and info["recent_terminal"][-1]["status"] == "completed"


def test_office_status_for_missing_office_is_safe(vault, offices):
    info = office_status("yok", vault_path=vault)
    assert info["exists"] is False and info["running"] == []


# ---------------------------------------------------------------------------
# 5.4 — sağlayıcı durum probu
# ---------------------------------------------------------------------------


class FakeRun:
    """subprocess.run taklidi: komuta göre hazır çıktı."""

    def __init__(self, stdout="", stderr="", returncode=0, raises=None):
        self.stdout, self.stderr, self.returncode, self.raises = stdout, stderr, returncode, raises
        self.cmds = []

    def __call__(self, cmd, **kwargs):
        self.cmds.append(cmd)
        if self.raises:
            raise self.raises
        return self


def test_probe_claude_parses_auth_status_json():
    """Gerçek `claude auth status --json` alan adlarıyla (loggedIn/email/subscriptionType)."""
    runner = FakeRun(stdout=json.dumps({
        "loggedIn": True, "authMethod": "claude.ai", "email": "kisi@example.com",
        "orgName": "Org", "subscriptionType": "max",
    }))
    status = probe_claude(runner=runner)
    assert status.provider == "claude" and status.logged_in is True
    assert status.account_hint == "kisi@example.com"
    assert status.plan == "max" and status.quota_hint == "abonelik: max"
    assert status.last_error == "" and status.checked_at
    assert runner.cmds[0][1:] == ["auth", "status", "--json"]


def test_probe_claude_handles_logged_out_and_broken_output():
    out = probe_claude(runner=FakeRun(stdout=json.dumps({"loggedIn": False})))
    assert out.logged_in is False and out.last_error == "oturum kapalı"

    broken = probe_claude(runner=FakeRun(stdout="not json", stderr="boom"))
    assert broken.logged_in is False and "boom" in broken.last_error

    missing = probe_claude(runner=FakeRun(raises=FileNotFoundError("claude yok")))
    assert missing.logged_in is False and "claude yok" in missing.last_error


def test_probe_agy_uses_models_listing_and_reports_unknown_quota(monkeypatch, tmp_path):
    """agy'de oturum/kota alt komutu yok; kota 'bilinmiyor' kalmalı."""
    home = tmp_path / "gemini"
    home.mkdir()
    (home / "google_accounts.json").write_text(
        json.dumps({"active": "kisi@example.com"}), encoding="utf-8")
    (home / "oauth_creds.json").write_text(
        json.dumps({"expiry_date": 4102444800000}), encoding="utf-8")
    monkeypatch.setattr("entropy.core.identity.GEMINI_HOME", home)

    status = probe_agy(runner=FakeRun(stdout="gemini-3.1-pro-high\tGemini 3.1 Pro"))
    assert status.logged_in is True
    assert status.account_hint == "kisi@example.com"
    assert status.quota_hint == "bilinmiyor"
    assert "belirteç" in status.session_window

    dead = probe_agy(runner=FakeRun(stdout="", stderr="unauthenticated", returncode=1))
    assert dead.logged_in is False and "unauthenticated" in dead.last_error


def test_identity_layer_caches_and_emits(monkeypatch, qapp):
    layer = IdentityLayer()
    monkeypatch.setattr(
        "entropy.core.identity.PROBES",
        {
            "claude": lambda runner=None: ProviderStatus(provider="claude", logged_in=True,
                                                         plan="max"),
            "agy": lambda runner=None: ProviderStatus(provider="agy", logged_in=False,
                                                      last_error="oturum yok"),
        },
    )
    from entropy.core.event_bus import bus

    seen = {}
    bus.provider_status_updated.connect(lambda p, d: seen.__setitem__(p, d))

    out = layer.refresh_all()
    assert out["claude"].logged_in is True and out["agy"].logged_in is False
    assert layer.get("claude").plan == "max"
    assert seen["agy"]["last_error"] == "oturum yok"
    assert layer.get("claude").badge.startswith("claude:")
    assert "giriş yok" in layer.get("agy").badge


def test_identity_layer_survives_probe_exception(monkeypatch):
    layer = IdentityLayer()

    def boom(runner=None):
        raise RuntimeError("prob patladı")

    monkeypatch.setattr("entropy.core.identity.PROBES", {"agy": boom, "claude": boom})
    status = layer.refresh("agy")
    assert status.logged_in is False and "prob patladı" in status.last_error


def test_login_command_is_guidance_only_and_calls_no_model(monkeypatch):
    from entropy.core.slash_commands import try_handle_local_command

    monkeypatch.setattr(
        "entropy.core.identity.PROBES",
        {
            "claude": lambda runner=None: ProviderStatus(provider="claude", logged_in=False),
            "agy": lambda runner=None: ProviderStatus(provider="agy", logged_in=True,
                                                      account_hint="a@b.c"),
        },
    )
    out = try_handle_local_command("/login", bridge=None)
    assert "claude login" in out          # yönlendirme metni
    assert "a@b.c" in out                 # açık oturumun hesabı
    assert "giriş yok" in out

    bad = try_handle_local_command("/login gemini", bridge=None)
    assert "Bilinmeyen sağlayıcı" in bad


def test_login_guidance_texts_exist():
    assert "claude login" in login_guidance("claude")
    assert "agy models" in login_guidance("agy")
    assert login_guidance("yok") == "Bilinmeyen sağlayıcı."


# ---------------------------------------------------------------------------
# 5.4 — Claude "Entropy profili" (CLAUDE_CONFIG_DIR)
# ---------------------------------------------------------------------------


def test_claude_process_env_is_none_unless_profile_configured(tmp_path, monkeypatch):
    from entropy.core.claude_bridge import ClaudeCodeBridge
    from entropy.core.config import config

    monkeypatch.setattr(config, "claude_config_dir", "", raising=False)
    assert ClaudeCodeBridge.process_env() is None, "boş ayar kullanıcının profilini bozmamalı"

    monkeypatch.setattr(config, "claude_config_dir", str(tmp_path / "profil"), raising=False)
    env = ClaudeCodeBridge.process_env()
    assert env["CLAUDE_CONFIG_DIR"] == str(tmp_path / "profil")
    assert (tmp_path / "profil").is_dir()


# ---------------------------------------------------------------------------
# 5.4 — konuşma eşlemesi ve bayrak seçimi
# ---------------------------------------------------------------------------


def test_conversation_map_keeps_both_providers_and_picks_right_flag(tmp_path):
    cmap = ConversationMap(path=tmp_path / "conversation_map.json")
    cmap.set("conv-1", "agy", "agy-session-9")
    cmap.set("conv-1", "claude", "claude-session-7")

    assert cmap.resume_flag("conv-1", "agy") == ["--conversation", "agy-session-9"]
    assert cmap.resume_flag("conv-1", "claude") == ["--resume", "claude-session-7"]
    # Sağlayıcı değişip geri dönülünce eşleme korunmalı.
    assert sorted(cmap.providers_for("conv-1")) == ["agy", "claude"]
    assert cmap.get("conv-1", "agy") == "agy-session-9"
    # Eşleme yoksa bayrak YOK: uydurma kimlikle --resume CLI'ı hataya düşürüyordu.
    assert cmap.resume_flag("conv-2", "agy") == []
    assert cmap.resume_flag("conv-1", "bilinmeyen") == []

    assert cmap.forget("conv-1") is True
    assert cmap.resume_flag("conv-1", "agy") == []


def test_conversation_map_write_is_atomic_and_reloadable(tmp_path):
    path = tmp_path / "conversation_map.json"
    ConversationMap(path=path).set("c", "agy", "s1")
    assert json.loads(path.read_text(encoding="utf-8"))["c"]["agy"] == "s1"
    assert not list(tmp_path.glob("*.tmp*"))
    # Bozuk dosya eşlemeyi düşürmemeli.
    path.write_text("{bozuk", encoding="utf-8")
    assert ConversationMap(path=path).get("c", "agy") is None


def test_agy_real_bridge_adds_conversation_flag(tmp_path, monkeypatch):
    """
    GERÇEK `send_background_task_async` yolu (Popen taklidi): yeni parametre
    `conversation_id` argv'ye `--conversation <id>` olarak girmeli.

    Sahte köprüyle geçen bir test bu bayrağın hiç eklenmediğini gizlerdi.
    """
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))

    seen_cmds = []

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)

        def readline(self):
            return next(self._iter, "")

        def close(self):
            pass

    class DummyProc:
        def __init__(self, cmd, *args, **kwargs):
            seen_cmds.append(list(cmd))
            self.stdout = DummyStdout([
                '{"event": "result", "result": {"response": "devam ettim"}}\n', "",
            ])
            self.pid = 9911

        def wait(self):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    done = threading.Event()
    got = {}
    bridge.send_background_task_async(
        task_id="conv-real-1",
        task_name="Konuşma devamı",
        prompt="kısa soru",
        mode="accept-edits",
        on_result=lambda text, ok: (got.update(text=text, ok=ok), done.set()),
        save_report=False,
        conversation_id="agy-session-9",
    )
    assert done.wait(timeout=10), "on_result çağrılmadı"
    assert got["ok"] is True
    cmd = seen_cmds[0]
    assert "--conversation" in cmd
    assert cmd[cmd.index("--conversation") + 1] == "agy-session-9"


def test_claude_build_command_prefers_explicit_resume_id():
    from entropy.core.claude_bridge import ClaudeCodeBridge

    bridge = ClaudeCodeBridge()
    bridge.current_session_id = "etkilesimli-oturum"

    cmd = bridge.build_command("selam", resume_id="arka-plan-oturumu")
    assert cmd[cmd.index("--resume") + 1] == "arka-plan-oturumu", \
        "açık kimlik etkileşimli oturumun önüne geçmeli"

    cmd2 = bridge.build_command("selam", resume=True)
    assert cmd2[cmd2.index("--resume") + 1] == "etkilesimli-oturum"

    cmd3 = bridge.build_command("selam")
    assert "--resume" not in cmd3


# ---------------------------------------------------------------------------
# 5.4 — agentic sohbet
# ---------------------------------------------------------------------------


def test_agentic_chat_turn_uses_mailbox_both_ways(vault, offices, agents, tmp_path):
    cmap = ConversationMap(path=tmp_path / "cmap.json")
    bridge = ScriptedBridge(["Üç kaynak buldum."])
    chat = AgenticChat("conv-42", "arastirma-ofisi", target_kind="office",
                       vault_path=vault, bridge_factory=lambda p: bridge, cmap=cmap)

    turn = chat.send("hangi kaynaklar var?", timeout=5)
    assert turn is not None and turn.text == "Üç kaynak buldum."
    assert turn.role == "[🏢 arastirma-ofisi]" and turn.provider == "agy"

    # Giden: ofis kutusuna question. Gelen: Entropy kutusuna report.
    outgoing = office_mailbox("arastirma-ofisi", vault_path=vault).list()
    assert len(outgoing) == 1 and outgoing[0].kind == "question"
    assert outgoing[0].task_id == "conv-42"
    incoming = entropy_mailbox(vault_path=vault).list(kind="report")
    assert incoming and incoming[-1].text == "Üç kaynak buldum."
    assert incoming[-1].from_ == "arastirma-ofisi"

    # Yanıtı ofisin ORKESTRATÖRÜ üretmeli ve oturum eşlemeye yazılmalı.
    assert bridge.calls[0]["agent"] == "orkestrator"
    assert cmap.get("conv-42", "agy") == "conv-agy-1"


def test_agentic_chat_second_turn_resumes_same_session(vault, offices, agents, tmp_path):
    cmap = ConversationMap(path=tmp_path / "cmap.json")
    bridge = ScriptedBridge(["ilk", "ikinci"])
    chat = AgenticChat("conv-7", "arastirma-ofisi", vault_path=vault,
                       bridge_factory=lambda p: bridge, cmap=cmap)
    chat.send("soru 1", timeout=5)
    chat.send("soru 2", timeout=5)

    assert bridge.calls[0]["conversation_id"] is None, "ilk tur yeni oturum açar"
    assert bridge.calls[1]["conversation_id"] == "conv-agy-1", "ikinci tur devam etmeli"
    # İki taraf da aynı dökümde görünür.
    assert "[Entropy AI]" in chat.transcript() and "[🏢 arastirma-ofisi]" in chat.transcript()
    assert bridge.calls[1]["prompt"].count("[Entropy AI]") == 2


def test_agentic_chat_close_emits_terminal_event(vault, offices, agents, tmp_path):
    chat = AgenticChat("conv-9", "arastirma-ofisi", vault_path=vault,
                       bridge_factory=lambda p: ScriptedBridge([]),
                       cmap=ConversationMap(path=tmp_path / "cmap.json"))
    chat.close()
    assert has_terminal_event("conv-9", vault_path=vault)


def test_chat_command_validates_target(vault, offices, agents):
    from entropy.core.slash_commands import try_handle_local_command

    assert "adında ofis ya da ajan yok" in try_handle_local_command("/chat yok merhaba", None)
    assert "Mesaj boş olamaz" in try_handle_local_command("/chat arastirma-ofisi", None)
    assert "Kullanım" in try_handle_local_command("/chat", None)
