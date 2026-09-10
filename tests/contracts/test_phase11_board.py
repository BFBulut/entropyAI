"""
Faz 11-C — Entropy Board sözleşmeleri.

Kapsam: durum makinesi tablosu, olay günlüğü + projeksiyon, atomik sahiplenme,
açılış uzlaştırması, `/task` artık koşturmuyor, ajan oturum deposu ve argv,
efor uçtan uca, pano araçları, rapor sinyali.

Gerçek model çağrısı YOK: köprü yolu `subprocess.Popen` taklidiyle ölçülür.
"""

import json
import os
import sys
import threading
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from entropy.agents import board_fsm, board_tools  # noqa: E402
from entropy.agents.board_events import (  # noqa: E402
    BoardEventLog,
    projection_hash,
    render_taskboard_text,
    unmatched_runs,
)
from entropy.agents.dispatcher import (  # noqa: E402
    BoardDispatcherCore,
    ClaimStore,
)
from entropy.agents.registry import AgentRegistry, AgentSpec  # noqa: E402
from entropy.agents.tasks import TaskBoard, TaskCard, new_task_id  # noqa: E402
from entropy.core import paths as core_paths  # noqa: E402


# --------------------------------------------------------------------------
# fikstürler
# --------------------------------------------------------------------------

@pytest.fixture
def vault(tmp_path):
    root = tmp_path / "vault"
    (root / "Entropy" / "Tasks").mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


def make_card(board, agent="arastirmaci", **kw):
    card = TaskCard(
        id=kw.pop("id", new_task_id("test")),
        title=kw.pop("title", "Test kartı"),
        agent=agent,
        goal=kw.pop("goal", "Bir şey araştır"),
        **kw,
    )
    return board.create(card)


def seed_agent(vault, name="arastirmaci", **kw):
    reg = AgentRegistry(vault_path=vault)
    reg.create(AgentSpec(name=name, role=kw.pop("role", "Araştırmacı"),
                       provider=kw.pop("provider", "claude"), **kw))
    return reg


# --------------------------------------------------------------------------
# A. Durum makinesi
# --------------------------------------------------------------------------

def test_status_set_has_eight_values_and_table_has_twelve_rows():
    assert board_fsm.STATUSES == (
        "backlog", "assigned", "taken", "running",
        "review", "done", "failed", "canceled",
    )
    assert len(board_fsm.TRANSITIONS) == 12
    assert len(board_fsm.EVENTS) == 12
    # Tablodaki her olay sözlükte var (ve tersi, `task.reset` kaçış kapısı hariç).
    table_events = {t.event for t in board_fsm.TRANSITIONS}
    assert table_events <= set(board_fsm.EVENTS)
    assert set(board_fsm.EVENTS) - table_events == {"task.reset"}


@pytest.mark.parametrize("status,event,target", [
    ("backlog", "task.assigned", "assigned"),
    ("assigned", "task.claimed", "taken"),
    ("taken", "run.started", "running"),
    ("running", "checkpoint.written", "running"),
    ("running", "run.finished", "review"),
    ("taken", "claim.expired", "assigned"),
    ("running", "lock.timeout", "assigned"),
    ("review", "task.accepted", "done"),
    ("review", "task.rejected", "assigned"),
    ("running", "task.canceled", "canceled"),
])
def test_valid_transitions_reach_expected_target(status, event, target):
    card = {"id": "c1", "title": "t", "goal": "g", "status": status,
            "agent": "a", "provider": "claude", "attempt": 0, "proof": "kanıt"}
    payload = {"claimed": True, "claimed_by": "a", "agent": "a",
               "provider": "claude", "actor": board_fsm.HUMAN_ACTOR,
               "pid_alive": False, "ok": True}
    assert board_fsm.transition(card, event, payload)["status"] == target


@pytest.mark.parametrize("status,event", [
    ("backlog", "task.accepted"),      # doğrudan done olamaz
    ("backlog", "run.started"),        # sahiplenmeden koşamaz
    ("done", "task.rejected"),         # terminal
    ("canceled", "run.started"),
    ("review", "checkpoint.written"),
    ("assigned", "run.finished"),
])
def test_invalid_transitions_raise(status, event):
    card = {"id": "c1", "title": "t", "goal": "g", "status": status,
            "agent": "a", "provider": "claude", "attempt": 0}
    with pytest.raises(board_fsm.InvalidTransition):
        board_fsm.transition(card, event, {"actor": "human", "ok": True})


def test_backlog_to_done_is_rejected_with_reason():
    card = {"id": "c", "title": "t", "goal": "g", "status": "backlog", "agent": "a"}
    with pytest.raises(board_fsm.InvalidTransition) as err:
        board_fsm.transition(card, "task.accepted", {"actor": "human"})
    # Hata yönlendirici: bu durumdan hangi olayların yayılabileceğini söyler.
    assert "task.assigned" in str(err.value)


def test_done_requires_human_actor_and_proof():
    card = {"id": "c", "title": "t", "goal": "g", "status": "review",
            "agent": "a", "proof": "pytest -q — 12 passed"}
    with pytest.raises(board_fsm.InvalidTransition) as err:
        board_fsm.transition(card, "task.accepted", {"actor": "arastirmaci"})
    assert "insan" in str(err.value)
    no_proof = dict(card, proof="")
    with pytest.raises(board_fsm.InvalidTransition) as err2:
        board_fsm.transition(no_proof, "task.accepted", {"actor": "human"})
    assert "kanıt" in str(err2.value).lower()
    assert board_fsm.transition(card, "task.accepted",
                                {"actor": "human"})["status"] == "done"


def test_red_proof_sends_run_finished_to_failed():
    card = {"id": "c", "title": "t", "goal": "g", "status": "running",
            "agent": "a", "provider": "claude"}
    out = board_fsm.transition(card, "run.finished",
                               {"ok": True, "proof": {"green": False,
                                                      "command": "pytest",
                                                      "result": "1 failed"}})
    assert out["status"] == "failed"


def test_claim_without_lock_is_rejected():
    card = {"id": "c", "title": "t", "goal": "g", "status": "assigned", "agent": "a"}
    with pytest.raises(board_fsm.InvalidTransition) as err:
        board_fsm.transition(card, "task.claimed", {"claimed_by": "a"})
    assert "kilid" in str(err.value)


def test_reject_stops_after_attempt_ceiling():
    card = {"id": "c", "title": "t", "goal": "g", "status": "review",
            "agent": "a", "attempt": board_fsm.MAX_ATTEMPTS}
    with pytest.raises(board_fsm.InvalidTransition):
        board_fsm.transition(card, "task.rejected", {})


# --------------------------------------------------------------------------
# B. Olay günlüğü ve projeksiyon
# --------------------------------------------------------------------------

def test_full_lifecycle_writes_at_least_six_events(board, vault):
    card = make_card(board)
    board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    board.apply_event(card.id, "task.claimed",
                      payload={"claimed": True, "claimed_by": card.agent,
                               "claim_expiry": "2030-01-01T00:00:00"})
    board.apply_event(card.id, "run.started", payload={"provider": "claude"})
    board.apply_event(card.id, "checkpoint.written",
                      payload={"checkpoint": "cp.md"})
    board.apply_event(card.id, "run.finished",
                      payload={"ok": True, "summary": "bitti"})
    log = BoardEventLog(vault)
    events = [e for e in log.read() if e["task_id"] == card.id]
    # `task.created` `create()` içinde yazılmadığı için beş geçiş olayı + kart
    # yaratımı: yaşam döngüsü en az altı satır üretir.
    assert len(events) >= 5
    actions = [e["action"] for e in events]
    assert actions == ["task.assigned", "task.claimed", "run.started",
                       "checkpoint.written", "run.finished"]
    assert [e["seq"] for e in events] == sorted(e["seq"] for e in events)
    assert board.get(card.id).status == "review"


def test_event_log_is_append_only(board, vault):
    card = make_card(board)
    path = core_paths.board_events_path(vault)
    board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    first = path.read_text(encoding="utf-8")
    board.apply_event(card.id, "task.claimed",
                      payload={"claimed": True, "claimed_by": card.agent})
    second = path.read_text(encoding="utf-8")
    assert len(second) > len(first)
    assert second.startswith(first)  # hiçbir satır DEĞİŞMEDİ


def test_idempotency_key_blocks_duplicate_event(board, vault):
    card = make_card(board)
    log = BoardEventLog(vault)
    assert log.append("task.assigned", card.id, payload={"agent": "a"}) is not None
    assert log.append("task.assigned", card.id, payload={"agent": "a"}) is None
    assert len([e for e in log.read() if e["task_id"] == card.id]) == 1


def test_projection_is_deterministic(board, vault):
    card = make_card(board)
    board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    board.apply_event(card.id, "task.claimed",
                      payload={"claimed": True, "claimed_by": card.agent})
    board.apply_event(card.id, "run.started", payload={"provider": "claude"})
    log = BoardEventLog(vault)
    first = log.project()
    second = BoardEventLog(vault).project()
    assert first["projection_hash"] == second["projection_hash"]
    assert first["cards"][card.id]["status"] == "running"
    # Karma gerçekten içerikten türüyor: bir olay daha eklenince değişir.
    board.apply_event(card.id, "run.finished", payload={"ok": True, "summary": "x"})
    assert BoardEventLog(vault).project()["projection_hash"] != first["projection_hash"]


def test_projection_hash_ignores_its_own_field():
    view = {"last_seq": 3, "cards": {}}
    h = projection_hash(view)
    assert projection_hash({**view, "projection_hash": "deadbeef"}) == h


def test_taskboard_is_rendered_and_marked_derived(board, vault):
    card = make_card(board)
    board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    text = core_paths.board_taskboard_path(vault).read_text(encoding="utf-8")
    assert "elle düzenlemeyin" in text
    assert card.id in text
    assert "## assigned (1)" in text
    # Sekiz durumun hepsi sütun olarak görünür.
    for status in board_fsm.STATUSES:
        assert f"## {status} (" in text


def test_render_taskboard_text_is_pure():
    text = render_taskboard_text(
        [{"id": "c1", "title": "Başlık", "status": "running", "agent": "yazar",
          "priority": "P0", "effort": "high"}], last_seq=7, projection_hash="abc")
    assert "`c1` Başlık — yazar · P0 · high" in text
    assert "## running (1)" in text


def test_unmatched_run_started_is_detectable(board, vault):
    card = make_card(board)
    board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    board.apply_event(card.id, "task.claimed",
                      payload={"claimed": True, "claimed_by": card.agent})
    board.apply_event(card.id, "run.started", payload={"provider": "claude"})
    assert unmatched_runs(vault_path=vault) == [card.id]
    board.apply_event(card.id, "run.finished", payload={"ok": True, "summary": "s"})
    assert unmatched_runs(vault_path=vault) == []


# --------------------------------------------------------------------------
# C. Sahiplenme ve tetikleyici
# --------------------------------------------------------------------------

def test_claim_is_atomic_under_race(vault):
    store = ClaimStore(vault)
    results = []
    barrier = threading.Barrier(8)

    def worker(i):
        barrier.wait()
        results.append(store.acquire("kart-1", f"ajan{i}"))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    winners = [r for r in results if r is not None]
    assert len(winners) == 1, "iki dispatcher aynı kartı alamaz"
    assert len(results) == 8


def test_two_dispatcher_rounds_cannot_take_same_card(vault, monkeypatch):
    seed_agent(vault)
    board = TaskBoard(vault_path=vault)
    card = make_card(board)
    board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    started = []
    core_a = BoardDispatcherCore(board=board, vault_path=vault,
                                runner=lambda cid, spec: started.append(cid) or "task-1")
    core_b = BoardDispatcherCore(board=TaskBoard(vault_path=vault), vault_path=vault,
                                runner=lambda cid, spec: started.append(cid) or "task-2")
    core_a.tick()
    core_b.tick()
    assert started == [card.id]


def test_pick_orders_by_priority_then_created_at(vault):
    seed_agent(vault)
    board = TaskBoard(vault_path=vault)
    low = make_card(board, id="a-low", priority="P2", created_at="2026-01-01T00:00:00")
    high = make_card(board, id="b-high", priority="P0", created_at="2026-09-01T00:00:00")
    for c in (low, high):
        board.apply_event(c.id, "task.assigned", payload={"agent": c.agent})
    core = BoardDispatcherCore(board=board, vault_path=vault)
    picked = core.pick("arastirmaci")
    assert picked.id == high.id
    assert picked.status == "taken"
    assert picked.claimed_by == "arastirmaci"


def test_dispatcher_respects_max_parallel(vault):
    seed_agent(vault, name="a1")
    seed_agent(vault, name="a2")
    seed_agent(vault, name="a3")
    board = TaskBoard(vault_path=vault)
    for name in ("a1", "a2", "a3"):
        card = make_card(board, agent=name, id=f"card-{name}")
        board.apply_event(card.id, "task.assigned", payload={"agent": name})
    core = BoardDispatcherCore(board=board, vault_path=vault, max_parallel=2,
                              runner=lambda cid, spec: "task")
    started = core.tick()
    assert len(started) == 2
    waiting = [c for c in board.list(status="assigned")]
    assert len(waiting) == 1


def test_expired_claim_with_dead_pid_is_taken_over(vault):
    store = ClaimStore(vault, timeout_s=1)
    path = store.path_for("kart-x")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"card_id": "kart-x", "agent": "eski",
                                "pid": 999_999_999,
                                "expiry": "2000-01-01T00:00:00"}), encoding="utf-8")
    lease = store.acquire("kart-x", "yeni")
    assert lease is not None and lease["agent"] == "yeni"


def test_live_pid_claim_is_not_taken_over(vault):
    store = ClaimStore(vault, timeout_s=1)
    path = store.path_for("kart-y")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"card_id": "kart-y", "agent": "eski",
                                "pid": os.getppid() or os.getpid(),
                                "expiry": "2000-01-01T00:00:00"}), encoding="utf-8")
    assert store.acquire("kart-y", "yeni") is None


def test_reconcile_recovers_hung_running_card(vault):
    seed_agent(vault)
    board = TaskBoard(vault_path=vault)
    card = make_card(board)
    board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    board.apply_event(card.id, "task.claimed",
                      payload={"claimed": True, "claimed_by": card.agent})
    board.apply_event(card.id, "run.started", payload={"provider": "claude"})
    # Kilit ölü bir sürece ait: uygulama koşu sırasında kapanmış.
    store = ClaimStore(vault)
    store.dir.mkdir(parents=True, exist_ok=True)
    store.path_for(card.id).write_text(
        json.dumps({"card_id": card.id, "agent": card.agent, "pid": 999_999_999,
                    "expiry": "2000-01-01T00:00:00"}), encoding="utf-8")
    assert board.get(card.id).status == "running"
    recovered = BoardDispatcherCore(board=board, vault_path=vault).reconcile()
    assert recovered == [card.id]
    assert board.get(card.id).status == "assigned"
    assert not store.path_for(card.id).exists()


# --------------------------------------------------------------------------
# D. `/task` artık koşturmuyor
# --------------------------------------------------------------------------

def test_slash_task_creates_card_without_running(monkeypatch):
    from entropy.core import slash_commands
    from entropy.core.config import config

    # `/task` VARSAYILAN kasada koşar (conftest onu tmp'ye yönlendiriyor);
    # ajanı da oraya ekiyoruz ki komut kendi yolunu bulsun.
    seed_agent(config.obsidian_vault_path)
    calls = []
    monkeypatch.setattr(TaskBoard, "run",
                        lambda self, *a, **kw: calls.append(a) or "task-x")
    started = []

    class FakeDispatcher:
        def start(self):
            started.append(True)
            return True

    monkeypatch.setattr("entropy.agents.dispatcher.board_dispatcher",
                        lambda create=True: FakeDispatcher())
    out = slash_commands._handle_task("arastirmaci Rapor yaz :: bir rapor yaz")
    assert "Panoya" in out
    assert calls == [], "/task artık board.run çağırmamalı"
    assert started == [True], "/task tetikleyiciyi uyandırmalı"
    board = TaskBoard()
    cards = board.list()
    assert len(cards) == 1 and cards[0].status == "assigned"


# --------------------------------------------------------------------------
# E. Ajan oturum deposu ve argv
# --------------------------------------------------------------------------

def test_agent_session_store_is_deterministic_and_persistent(vault):
    from entropy.core.identity import AgentSessionStore

    store = AgentSessionStore(vault)
    uid = AgentSessionStore.claude_session_id("yazar")
    assert uid == AgentSessionStore.claude_session_id("yazar")
    first = store.run_kwargs("yazar", "claude", model="claude-opus-5",
                             effort="high", system_prompt="P")
    assert first == {"session_id": uid}
    # İkinci koşu aynı imza → sürdürme.
    second = AgentSessionStore(vault).run_kwargs(
        "yazar", "claude", model="claude-opus-5", effort="high", system_prompt="P")
    assert second == {"conversation_id": uid}
    assert core_paths.agent_session_path("yazar", vault).is_file()


def test_session_drops_when_model_or_effort_changes(vault):
    from entropy.core.identity import AgentSessionStore

    store = AgentSessionStore(vault)
    store.run_kwargs("yazar", "claude", model="m1", effort="low", system_prompt="P")
    assert store.run_kwargs("yazar", "claude", model="m1", effort="low",
                            system_prompt="P").get("conversation_id")
    # Efor değişti → yeni oturum (resume YOK).
    out = store.run_kwargs("yazar", "claude", model="m1", effort="high",
                           system_prompt="P")
    assert "conversation_id" not in out and "session_id" in out
    # Model değişti → yine yeni oturum.
    store.run_kwargs("yazar", "claude", model="m1", effort="high", system_prompt="P")
    out2 = store.run_kwargs("yazar", "claude", model="m2", effort="high",
                            system_prompt="P")
    assert "conversation_id" not in out2


def test_prompt_signature_covers_model_and_effort():
    from entropy.core.identity import ConversationMap

    base = ConversationMap.prompt_signature("P")
    assert ConversationMap.prompt_signature("P") == base
    assert ConversationMap.prompt_signature("P", "m1") != base
    assert ConversationMap.prompt_signature("P", "m1", "low") != \
        ConversationMap.prompt_signature("P", "m1", "high")


def test_agy_session_is_captured_from_stream(vault):
    from entropy.core.identity import AgentSessionStore

    store = AgentSessionStore(vault)
    assert store.run_kwargs("yazar", "agy", model="gemini-3.8-flash-high",
                            system_prompt="P") == {}
    store.record_captured("yazar", "agy", "conv_42")
    out = store.run_kwargs("yazar", "agy", model="gemini-3.8-flash-high",
                           system_prompt="P")
    assert out == {"conversation_id": "conv_42"}


def test_claude_build_command_carries_effort_and_session_id():
    from entropy.core.claude_bridge import ClaudeCodeBridge

    bridge = ClaudeCodeBridge()
    cmd = bridge.build_command("merhaba", effort="low",
                               session_id="11111111-2222-3333-4444-555555555555")
    assert "--effort" in cmd and cmd[cmd.index("--effort") + 1] == "low"
    assert "--session-id" in cmd
    assert "--resume" not in cmd
    # Sürdürme kimliği varken `--session-id` verilmez.
    resumed = bridge.build_command("merhaba", effort="high", resume_id="abc",
                                   session_id="def")
    assert "--resume" in resumed and "--session-id" not in resumed
    # Prompt'taki tek seferlik `/effort` çağrının eforunu ezer.
    override = bridge.build_command("/effort max iş", effort="low")
    assert override[override.index("--effort") + 1] == "max"


def test_claude_agents_json_carries_effort(vault):
    from entropy.agents.compile import claude_agents_json

    seed_agent(vault, name="yazar", effort="high")
    payload = json.loads(claude_agents_json(vault_path=vault))
    assert payload["yazar"]["effort"] == "high"


def test_agy_effort_is_a_model_suffix_not_a_flag(vault):
    from entropy.core.agy_bridge import AgyProcessBridge

    bridge = AgyProcessBridge()
    composed = bridge.apply_effort_to_model("gemini-3.8-flash-low", "high")
    assert composed.endswith("-high")
    # agy'de `--effort` bayrağı kullanılmaz (model adıyla çakışıyor).
    assert bridge.effort_for_prompt("iş", default_effort="medium") in bridge.effort_levels()


def test_card_effort_overrides_agent_effort(vault):
    from entropy.agents.tasks import agent_spec_payload, resolve_card_effort

    spec = AgentSpec(name="yazar", effort="low")
    card = TaskCard(id="c", title="t", effort="high")
    assert resolve_card_effort(card, agent_spec=spec) == "high"
    assert resolve_card_effort(TaskCard(id="c", title="t"), agent_spec=spec) == "low"
    assert agent_spec_payload(spec)["effort"] == "low"


def test_card_effort_is_a_real_frontmatter_field(board):
    card = make_card(board, effort="high", priority="P0",
                     input_paths=["src/x.py"], notes="önemli not")
    again = board.get(card.id)
    assert again.effort == "high"
    assert again.priority == "P0"
    assert again.input_paths == ["src/x.py"]
    # `notes` hilesi kalktı: efor alanı notu EZMİYOR.
    assert again.notes == "önemli not"


# --------------------------------------------------------------------------
# F. Pano araçları
# --------------------------------------------------------------------------

def test_agent_sees_exactly_four_board_tools_entropy_five():
    assert board_tools.tool_names() == ("board_next", "board_checkpoint",
                                        "board_finish", "board_ask")
    assert len(board_tools.tool_names(for_entropy=True)) == 5
    # Reddedilen araçlar gerçekten yok.
    for banned in ("board_move", "board_set_status", "board_list", "board_assign"):
        assert banned not in board_tools.ALL_TOOLS


def test_tools_section_stays_within_token_budget():
    text = board_tools.tools_section(for_entropy=True)
    # Kaba ölçü: ~4 karakter ≈ 1 token; hedef ≤ 800 token.
    assert len(text) / 4 < 800
    assert "board_create" in text
    assert "board_create" not in board_tools.tools_section()


def test_parse_tool_calls_reads_blocks():
    text = (
        "önce biraz metin\n"
        "[PANO board_checkpoint]\n"
        '{"task_id": "c1", "done": "modül A", "next": "modül B"}\n'
        "[/PANO]\n"
        "sonra biraz daha\n"
        "[PANO board_finish]\n"
        '{"task_id": "c1", "summary": "bitti",'
        ' "proof": {"command": "pytest -q", "result": "3 passed", "green": true}}\n'
        "[/PANO]\n"
    )
    calls = board_tools.parse_tool_calls(text)
    assert [c.name for c in calls] == ["board_checkpoint", "board_finish"]
    assert calls[0].args["done"] == "modül A"
    assert board_tools.validate_finish(calls[1].args) is None


def test_parse_skips_broken_json_without_raising():
    calls = board_tools.parse_tool_calls("[PANO board_finish]\n{bozuk\n[/PANO]")
    assert calls == []


def test_finish_without_proof_is_rejected_and_stays_in_review():
    args = {"task_id": "c1", "summary": "bitti"}
    reason = board_tools.validate_finish(args)
    assert reason and "pytest" in reason  # hata mesajı YÖNLENDİRİCİ
    status, why = board_tools.finish_outcome(args)
    assert status == "review" and why
    green = {"task_id": "c1", "summary": "s",
             "proof": {"command": "pytest -q", "result": "3 passed", "green": True}}
    assert board_tools.finish_outcome(green) == ("review", None)
    red = {"task_id": "c1", "summary": "s",
           "proof": {"command": "pytest -q", "result": "1 failed", "green": False}}
    assert board_tools.finish_outcome(red)[0] == "failed"


def test_board_next_payload_is_concise_and_trimmed():
    card = TaskCard(id="c1", title="Başlık", agent="yazar", goal="hedef",
                    criteria=[f"ö{i}" for i in range(30)],
                    input_paths=[f"f{i}.py" for i in range(60)])
    out = board_tools.normalize_next(card)
    assert len(out["criteria"]) == board_tools.CRITERIA_LIMIT
    assert len(out["input_paths"]) == board_tools.INPUT_PATHS_LIMIT
    assert out["agent"] == "yazar"
    assert "uuid" not in json.dumps(out)


# --------------------------------------------------------------------------
# G. Rapor sohbete
# --------------------------------------------------------------------------

def test_finished_entropy_card_emits_report_and_mail(board, vault, monkeypatch):
    from entropy.core.event_bus import bus

    seen = []
    bus.task_report_ready.connect(seen.append)
    try:
        card = make_card(board)
        board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
        board.apply_event(card.id, "task.claimed",
                          payload={"claimed": True, "claimed_by": card.agent})
        board.apply_event(card.id, "run.started", payload={"provider": "claude"})
        board._finish(card.id, "işi bitirdim", True)
    finally:
        bus.task_report_ready.disconnect(seen.append)
    assert seen and seen[0]["card_id"] == card.id
    assert seen[0]["ok"] is True
    assert "bitirdim" in seen[0]["summary"]
    # Entropy gelen kutusuna rapor düştü.
    from entropy.agents.mailbox import entropy_mailbox

    msgs = entropy_mailbox(vault_path=vault).list()
    assert any(getattr(m, "kind", "") == "report" for m in msgs)


def test_board_state_changed_is_emitted_per_transition(board):
    from entropy.core.event_bus import bus

    seen = []
    bus.board_state_changed.connect(seen.append)
    try:
        card = make_card(board)
        board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    finally:
        bus.board_state_changed.disconnect(seen.append)
    assert seen[-1]["card_id"] == card.id
    assert seen[-1]["status"] == "assigned"
    assert seen[-1]["event"] == "task.assigned"


def test_finish_with_red_proof_block_fails_card(board):
    card = make_card(board)
    board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    board.apply_event(card.id, "task.claimed",
                      payload={"claimed": True, "claimed_by": card.agent})
    board.apply_event(card.id, "run.started", payload={"provider": "claude"})
    board._finish(card.id,
                  '[PANO board_finish]\n{"task_id": "x", "summary": "s",'
                  ' "proof": {"command": "pytest", "result": "1 failed",'
                  ' "green": false}}\n[/PANO]', True)
    assert board.get(card.id).status == "failed"


def test_finish_with_green_proof_records_proof_field(board):
    card = make_card(board)
    board.apply_event(card.id, "task.assigned", payload={"agent": card.agent})
    board.apply_event(card.id, "task.claimed",
                      payload={"claimed": True, "claimed_by": card.agent})
    board.apply_event(card.id, "run.started", payload={"provider": "claude"})
    board._finish(card.id,
                  '[PANO board_finish]\n{"task_id": "x", "summary": "s",'
                  ' "proof": {"command": "pytest -q", "result": "9 passed",'
                  ' "green": true}, "outputs": ["out.md"]}\n[/PANO]', True)
    done = board.get(card.id)
    assert done.status == "review"
    assert "pytest -q" in done.proof and "9 passed" in done.proof
    assert "out.md" in done.output_paths


def test_entropy_card_prompt_carries_board_tools_office_card_does_not(board):
    card = make_card(board)
    prompt = board.build_prompt(card)
    assert "[PANO board_next]" in prompt
    assert "[PANO board_finish]" in prompt
    assert "board_create" not in prompt  # ajanın aracı DEĞİL
    office_card = board.create(TaskCard(id="ofis-1", title="Ofis işi",
                                        office="bir-ofis", agent="isci", goal="h"))
    assert "[PANO board_next]" not in board.build_prompt(office_card)
