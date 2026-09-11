"""
Faz 12-B: otonom pano — araç yürütücüsü, özet temizleyici, Entropy'nin kendi
kararıyla görev üretmesi, oturum bütçesi, projeksiyon/ayrışma, slash birleştirme.

Araştırma C (`docs/reports/2026-09-10_Faz12_Arastirma_C_...`) altı boşluk ölçtü;
bu dosya altısının da kapandığını ölçer. Model çağrısı YOK: köprüler sahte,
kasa `tmp_path` altında.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from entropy.agents import (board_autonomy, board_events, board_fsm,
                            board_tool_exec, board_tools, session_budget)
from entropy.agents.tasks import TaskBoard, TaskCard
from entropy.core import response_hooks, slash_commands as sc


@pytest.fixture
def board(tmp_path):
    return TaskBoard(vault_path=tmp_path)


def _card(board, **fields) -> TaskCard:
    data = dict(id=fields.pop("id", "k1"), title="Kart", agent="arastirmaci",
                goal="hedef", status="backlog")
    data.update(fields)
    return board.create(TaskCard(**data))


def _call(name: str, **args):
    return board_tools.ToolCall(name=name, args=args)


# --------------------------------------------------------------------------
# 1. Araç yürütücüsü — beş aracın hepsi tüketiliyor
# --------------------------------------------------------------------------


def test_checkpoint_tool_writes_file_and_fills_card_field(board, tmp_path):
    card = _card(board)
    res = board_tool_exec.execute(
        [_call("board_checkpoint", task_id=card.id, done="modül 1 bitti",
               next="modül 2", files=["a.py"], tests="pytest -q → 3 passed")],
        board=board, card=card, actor="arastirmaci", vault_path=tmp_path,
    )
    assert res[0]["ok"], res
    written = board.get(card.id)
    assert written.checkpoint, "kart `checkpoint` alanı hâlâ boş (G2)"
    assert res[0]["path"], "kontrol noktası dosyası yazılmadı"


def test_ask_tool_reaches_entropy_inbox_without_changing_status(board, tmp_path):
    from entropy.agents.mailbox import entropy_mailbox

    card = _card(board, status="running")
    res = board_tool_exec.execute(
        [_call("board_ask", task_id=card.id, question="Hangi kasa yolu?")],
        board=board, card=card, actor="arastirmaci", vault_path=tmp_path,
    )
    assert res[0]["ok"], res
    msgs = entropy_mailbox(tmp_path).list(kind="question")
    assert len(msgs) == 1 and "Hangi kasa yolu?" in msgs[0].text
    after = board.get(card.id)
    assert after.status == "running", "board_ask kartın DURUMUNU değiştirmemeli"
    assert after.review == board_tool_exec.ASK_REVIEW_TEXT
    assert board_tool_exec.ASK_NOTE_PREFIX in after.notes


def test_office_agent_cannot_ask_entropy(board, tmp_path):
    card = _card(board, office="stüdyo")
    res = board_tool_exec.execute(
        [_call("board_ask", task_id=card.id, question="?")],
        board=board, card=card, actor="orkestrator", vault_path=tmp_path,
    )
    assert not res[0]["ok"] and "ofis" in res[0]["error"].lower()


def test_next_tool_returns_next_assigned_card_or_none(board, tmp_path):
    done = _card(board, id="k-bitti", status="review")
    res = board_tool_exec.execute([_call("board_next", agent="arastirmaci")],
                                  board=board, card=done, vault_path=tmp_path)
    assert res[0]["result"] == "yok"

    _card(board, id="k-sonraki", status="assigned", title="Sıradaki")
    res = board_tool_exec.execute([_call("board_next", agent="arastirmaci")],
                                  board=board, card=done, vault_path=tmp_path)
    assert res[0]["result"] == "var"
    assert res[0]["next"]["task_id"] == "k-sonraki"


def test_board_create_is_rejected_for_agents(board, tmp_path):
    card = _card(board)
    res = board_tool_exec.execute([_call("board_create", title="X")],
                                  board=board, card=card,
                                  actor_kind=board_tool_exec.ACTOR_AGENT,
                                  vault_path=tmp_path)
    assert not res[0]["ok"], "ajan kart açamaz (yalnızca Entropy)"


# --------------------------------------------------------------------------
# 2. Özet temizleyici — sızıntı 0
# --------------------------------------------------------------------------


DIRTY = """Rapor gövdesi burada.

[KONTROL NOKTASI]
yapılan: modül 1
sonraki: modül 2

[KANIT]
komut: pytest -q
sonuç: yeşil

[KURAL] bu proje uv kullanır

[PANO board_finish]
{"task_id": "k1", "summary": "bitti",
 "proof": {"command": "pytest -q", "result": "3 passed", "green": true}}
[/PANO]

Son cümle."""

LEAK_NEEDLES = ("[PANO", "[/PANO]", "[KONTROL NOKTASI]", "[KANIT]", "[KURAL]")


def test_strip_tool_blocks_removes_every_block_but_keeps_prose():
    clean = board_tools.strip_tool_blocks(DIRTY)
    assert not any(n in clean for n in LEAK_NEEDLES), clean
    assert "Rapor gövdesi burada." in clean and "Son cümle." in clean


def test_finished_card_summary_and_report_payload_have_zero_leak(board, tmp_path):
    from entropy.core.event_bus import bus

    payloads = []
    bus.task_report_ready.connect(payloads.append)
    try:
        card = _card(board, status="running", id="k-temiz")
        board._finish(card.id, DIRTY, True)
    finally:
        bus.task_report_ready.disconnect(payloads.append)

    after = board.get("k-temiz")
    assert not any(n in (after.summary or "") for n in LEAK_NEEDLES)
    # Olay günlüğü HAM metni de taşımaz (özet oradan geliyor) ama kanıt yükü
    # korunur: close-with-proof ölçülebilir kalmalı.
    events = board.events.read()
    finished = [e for e in events if e["action"] == "run.finished"]
    assert finished and finished[-1]["payload"].get("proof", {}).get("green") is True
    if payloads:
        assert not any(n in str(payloads[-1].get("summary") or "")
                       for n in LEAK_NEEDLES)


# --------------------------------------------------------------------------
# 3. Entropy'nin kendi kararıyla görev üretmesi
# --------------------------------------------------------------------------


class _Registry:
    """Sahte Entropy kadrosu."""

    class Spec:
        def __init__(self, name):
            self.name = name
            self.provider = "agy"
            self.model = ""
            self.skills = []

    def __init__(self, names=("arastirmaci",)):
        self._specs = [self.Spec(n) for n in names]

    def list(self):
        return list(self._specs)

    def get(self, name):
        return next((s for s in self._specs if s.name == name), None)


def test_chat_response_block_creates_card_and_leaves_receipt(board, tmp_path):
    text = ('Bunu araştırmacıya veriyorum.\n\n'
            '[PANO board_create]\n'
            '{"title": "GIL notu", "goal": "kısa not", "agent": "arastirmaci"}\n'
            '[/PANO]\n')
    out = response_hooks.process_chat_response(text, board=board,
                                               registry=_Registry())
    assert "[PANO" not in out
    assert board_autonomy.RECEIPT_PREFIX in out and "GIL notu" in out

    cards = [c for c in board.list() if c.title == "GIL notu"]
    assert len(cards) == 1
    assert cards[0].agent == "arastirmaci"
    assert cards[0].status == "assigned", "tetikleyici yalnızca `assigned` kartı çeker"
    assert cards[0].path.is_file()
    actions = [e["action"] for e in board.events.read() if e["task_id"] == cards[0].id]
    assert "task.assigned" in actions


def test_unknown_agent_falls_back_to_backlog_with_note(board, tmp_path):
    out = response_hooks.process_chat_response(
        '[PANO board_create]\n{"title": "X", "agent": "yok-boyle-biri"}\n[/PANO]',
        board=board, registry=_Registry())
    card = [c for c in board.list() if c.title == "X"][0]
    assert card.status == "backlog" and not card.agent
    assert "kadrosunda yok" in card.notes
    assert board_autonomy.RECEIPT_PREFIX in out


def test_invalid_json_block_is_ignored_and_logged(board, tmp_path, caplog):
    text = '[PANO board_create]\n{bozuk json,,,}\n[/PANO]\nnormal metin'
    out = response_hooks.process_chat_response(text, board=board,
                                               registry=_Registry())
    assert board.list() == []
    assert "[PANO" not in out and "normal metin" in out


def test_turn_cap_is_one_card(board, tmp_path):
    text = ('[PANO board_create]\n{"title": "A"}\n[/PANO]\n'
            '[PANO board_create]\n{"title": "B"}\n[/PANO]')
    out = response_hooks.process_chat_response(text, board=board,
                                               registry=_Registry())
    assert len(board.list()) == board_autonomy.MAX_CARDS_PER_TURN == 1
    assert "yok sayıldı" in out


def test_entropy_tools_section_contains_board_create():
    section = response_hooks.entropy_tools_section()
    assert "[PANO board_create]" in section
    assert "[PANO board_finish]" in section, "ajan araçları da Entropy'ye görünür"


@pytest.mark.parametrize("bridge_cls", ["agy", "claude"])
def test_both_bridges_route_chat_text_through_the_same_hook(bridge_cls, monkeypatch):
    """İki köprü de `finalize_chat_text` ile aynı kancadan geçer (sözleşme)."""
    if bridge_cls == "agy":
        from entropy.core.agy_bridge import AgyProcessBridge as Cls
    else:
        from entropy.core.claude_bridge import ClaudeCodeBridge as Cls

    seen = {}
    monkeypatch.setattr(
        "entropy.core.response_hooks.process_chat_response",
        lambda text, **kw: seen.setdefault("text", text) and "" or "temiz",
    )
    bridge = Cls()
    assert bridge.finalize_chat_text("ham [KURAL] metin") == "temiz"
    assert seen["text"] == "ham [KURAL] metin"


# --------------------------------------------------------------------------
# 4. Oturum bütçesi
# --------------------------------------------------------------------------


def test_session_rotates_after_card_cap_and_writes_handoff(board, tmp_path, monkeypatch):
    from entropy.core.config import config
    from entropy.core.identity import AgentSessionStore

    monkeypatch.setattr(config, "agent_session_max_cards", 3, raising=False)
    monkeypatch.setattr(config, "agent_session_max_tokens", 60000, raising=False)

    store = AgentSessionStore(tmp_path)
    first = store.run_kwargs("arastirmaci", "claude", model="claude-opus-5",
                             effort="low", system_prompt="kimlik")
    assert "session_id" in first
    # Üç kart koştu: her biri sayaca işlendi.
    for i in range(3):
        c = board.create(TaskCard(id=f"kart-{i}", title=f"Kart {i}",
                                  agent="arastirmaci", status="review",
                                  summary=f"{i}. kartın özeti", provider="claude",
                                  checkpoint="sonraki: modül 2"))
        store.note_run("arastirmaci", "claude", tokens=20000)
        assert c.id

    status = store.budget_status("arastirmaci", "claude", max_cards=3, max_tokens=60000)
    assert status["exceeded"] and status["cards_in_session"] == 3

    block = session_budget.rotate_if_needed("arastirmaci", "claude",
                                            board=board, vault_path=tmp_path)
    assert session_budget.HANDOFF_TAG in block
    path = session_budget.handoff_path("arastirmaci", tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "## Yapılanlar" in text and "0. kartın özeti" in text
    assert "## Açık işler" in text and "modül 2" in text

    # 4. kart TAZE oturumda başlar (aynı kimlik yeniden verilmez: R1).
    fourth = store.run_kwargs("arastirmaci", "claude", model="claude-opus-5",
                              effort="low", system_prompt="kimlik")
    assert "session_id" in fourth, "4. kart hâlâ --resume ile koşuyor"
    assert fourth["session_id"] != first["session_id"]
    assert store.budget_status("arastirmaci", "claude")["cards_in_session"] == 0


def test_token_cap_also_rotates(tmp_path, monkeypatch):
    from entropy.core.config import config
    from entropy.core.identity import AgentSessionStore

    monkeypatch.setattr(config, "agent_session_max_cards", 0, raising=False)
    monkeypatch.setattr(config, "agent_session_max_tokens", 60000, raising=False)
    store = AgentSessionStore(tmp_path)
    store.run_kwargs("yazar", "agy", model="m", effort="low", system_prompt="p")
    store.note_run("yazar", "agy", tokens=66542)
    assert store.budget_status("yazar", "agy", max_tokens=60000)["exceeded"]
    session_budget.rotate_if_needed("yazar", "agy", vault_path=tmp_path)
    entry = store.get("yazar", "agy")
    assert not entry.get("conversation_id"), "agy'de --conversation düşmeliydi"
    assert entry["cards_in_session"] == 0


def test_budget_disabled_keeps_resume(tmp_path, monkeypatch):
    from entropy.core.config import config
    from entropy.core.identity import AgentSessionStore

    monkeypatch.setattr(config, "agent_session_max_cards", 0, raising=False)
    monkeypatch.setattr(config, "agent_session_max_tokens", 0, raising=False)
    store = AgentSessionStore(tmp_path)
    store.run_kwargs("yazar", "claude", model="m", effort="low", system_prompt="p")
    store.note_run("yazar", "claude", tokens=999999)
    assert session_budget.rotate_if_needed("yazar", "claude", vault_path=tmp_path) == ""


# --------------------------------------------------------------------------
# 5. projection.json + ayrışma uyarısı
# --------------------------------------------------------------------------


def test_projection_file_is_written_with_non_empty_hash(board, tmp_path):
    from entropy.core.paths import board_projection_path, board_taskboard_path

    card = _card(board, id="k-proj")
    board.apply_event(card.id, "task.assigned", actor="user",
                      payload={"agent": "arastirmaci"})
    path = board_projection_path(tmp_path)
    assert path.is_file(), "projection.json üretimde hâlâ yazılmıyor (G6)"
    view = json.loads(path.read_text(encoding="utf-8"))
    assert view["projection_hash"], "karma boş geçiliyor"
    board_text = board_taskboard_path(tmp_path).read_text(encoding="utf-8")
    assert view["projection_hash"][:16] in board_text


def test_drift_between_card_file_and_projection_is_reported(board, tmp_path, caplog):
    card = _card(board, id="k-drift")
    board.apply_event(card.id, "task.assigned", actor="user",
                      payload={"agent": "arastirmaci"})
    # Kart dosyası ELLE bozuluyor (kullanıcı Obsidian'da düzenledi).
    board.update(board.get("k-drift").__class__(
        **{**board.get("k-drift").__dict__, "status": "done", "path": None}))
    with caplog.at_level("WARNING"):
        board.rewrite_taskboard()
    assert any("ayrış" in r.message.lower() or "ayrış" in str(r.args)
               for r in caplog.records), caplog.text
    drift_events = [e for e in board.events.read() if e["action"] == "board.drift"]
    assert drift_events and drift_events[-1]["payload"]["count"] >= 1
    from entropy.core.paths import board_taskboard_path

    assert board_events.DRIFT_MARK in board_taskboard_path(tmp_path).read_text(encoding="utf-8")


def test_drift_event_does_not_poison_the_projection(board, tmp_path):
    """`board.drift` gözlem olayıdır: kart doğurmaz, `rejected` üretmez."""
    card = _card(board, id="k-info")
    board.apply_event(card.id, "task.assigned", actor="user",
                      payload={"agent": "arastirmaci"})
    before = board.events.project()
    board.events.append(action="board.drift", task_id=card.id, actor="system",
                        payload={"count": 1}, idempotency_key="drift:test")
    view = board.events.project()
    # Gözlem olayı ne reddedilen sayacını artırır ne de yeni kart doğurur.
    assert view["rejected"] == before["rejected"]
    assert set(view["cards"]) == set(before["cards"]) == {card.id}
    assert "board.drift" in board_fsm.EVENTS
    # Faz 13-C.4: ikinci bilgi olayı `board.archived` (arşivleme).
    assert board_fsm.INFO_EVENTS == ("board.drift", "board.archived")


# --------------------------------------------------------------------------
# 6. Slash birleştirme ve uzun komutların arka planı
# --------------------------------------------------------------------------


def test_local_command_surface_is_thirty_one():
    names = {c.name for c in sc.BUILTIN_AGY_COMMANDS + sc.LOCAL_COMMANDS}
    assert len(names) == 31, sorted(names)
    # Birleşen üçlü: `/agents`, `/tasks`, `/wiki` artık ayrı komut değil.
    assert {"/agents", "/tasks", "/wiki"}.isdisjoint(names)
    assert {"/agent", "/task", "/distill"} <= names


@pytest.mark.parametrize("alias,canonical", [("/agents", "/agent"),
                                             ("/tasks", "/task"),
                                             ("/wiki", "/distill wiki")])
def test_merged_aliases_still_answer(alias, canonical, monkeypatch):
    """Birleştirme kas hafızasını kırmaz: eski ad hâlâ yerel komut."""
    monkeypatch.setattr(sc, "_handle_agents", lambda bridge: "AJANLAR")
    monkeypatch.setattr(sc, "_handle_tasks", lambda args: "GÖREVLER")
    monkeypatch.setattr(sc, "_handle_wiki", lambda args, bridge=None: "WİKİ")
    out = sc.try_handle_local_command(alias, None)
    assert out is not None and out != ""


def test_long_memory_commands_do_not_block_the_caller(monkeypatch):
    import threading
    import time

    gate = threading.Event()

    def slow_round(memory=None, send_prompt=None, **kw):
        gate.wait(5)
        return {"merged": 1}

    monkeypatch.setattr("entropy.brain.gray_merge.run_merge_round", slow_round)
    started = time.time()
    out = sc._handle_memory("merge", None)
    elapsed = time.time() - started
    try:
        assert elapsed < 2.0, f"komut çağıranı bloklıyor ({elapsed:.1f} s)"
        assert "arka planda" in out
        assert sc.memory_job_running("memory-merge")
        # İptal: iş bir sonraki denetim noktasında durur.
        assert sc.cancel_memory_job("memory-merge")
    finally:
        gate.set()
        sc.reset_memory_jobs()


def test_memory_stop_reports_when_nothing_runs():
    sc.reset_memory_jobs()
    assert "Koşan hafıza turu yok" in sc._handle_memory("stop", None)


# --------------------------------------------------------------------------
# 7. Faz 12 kapanışı — `kind` sözleşmesi ve beyin kısayolu
# --------------------------------------------------------------------------


def test_board_create_always_fills_kind(board, tmp_path):
    """`kind` JSON'da yoksa sezgiyle doldurulur ve KARTA yazılır."""
    from entropy.agents import amplification

    # (a) açık `kind`
    created, _ = board_autonomy.create_card_from_args(
        {"title": "A", "goal": "x", "kind": "research"}, board=board)
    assert created.kind == "research"
    assert board.get(created.id).kind == "research"

    # (b) sezgi: "araştır ve raporu yaz" → research (eski sezgi bunu REDDEDİYORDU)
    created, _ = board_autonomy.create_card_from_args(
        {"title": "Vektör veritabanlarını araştır",
         "goal": "son gelişmeleri özetle ve raporu yaz"}, board=board)
    assert created.kind == "research", "yazma fiili araştırma kartını geri çekti"

    # (c) sezgi: kod kartı
    created, _ = board_autonomy.create_card_from_args(
        {"title": "Panoyu kodla", "goal": "dispatcher yaz"}, board=board)
    assert created.kind == "code"

    # (d) geçersiz `kind` sezgiye düşer, boş KALMAZ
    created, _ = board_autonomy.create_card_from_args(
        {"title": "Belirsiz iş", "goal": "bir şey", "kind": "zırva"}, board=board)
    assert created.kind in amplification.CARD_KINDS


def test_kind_contract_is_in_the_entropy_tool_text():
    text = board_tools.tools_section(for_entropy=True)
    assert '"kind"' in text
    for kind in ("research", "write", "code", "ops"):
        assert kind in text


class _FakeBridge:
    """Çağrıldığında istemi kaydeden sahte köprü."""

    def __init__(self):
        self.calls = []

    def send_background_task_async(self, **kwargs):
        self.calls.append(kwargs)


def _brain(monkeypatch, confidence: float, text: str = "Beyindeki yanıt."):
    from entropy.agents import amplification

    monkeypatch.setattr(
        amplification, "brain_lookup",
        lambda q, builder=None, card=None: amplification.BrainAnswer(
            has_answer=True, confidence=confidence, text=text))


def _registry_with(tmp_path, name="arastirmaci"):
    """GERÇEK ajan defteri: `resolve_model` AgentSpec sözleşmesine bağlı."""
    from entropy.agents.registry import AgentRegistry, AgentSpec

    reg = AgentRegistry(vault_path=tmp_path)
    if reg.get(name) is None:
        reg.create(AgentSpec(name=name, role="Araştırmacı", provider="claude",
                             tools_policy="read-only", prompt="Araştır."))
    return reg


def test_research_card_with_brain_answer_never_calls_cli(board, tmp_path, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "brain_confidence_threshold", 0.40, raising=False)
    _brain(monkeypatch, 0.88)
    card = _card(board, id="kind-r", title="Vektör veritabanlarını araştır",
                 goal="son gelişmeler", kind="research", provider="claude")
    board.apply_event(card.id, "task.assigned", payload={"agent": "arastirmaci"})

    bridge = _FakeBridge()
    task_id = board.run(card.id, bridge_factory=lambda p: bridge,
                        agent_registry=_registry_with(tmp_path))
    assert bridge.calls == [], "araştırma kartı için CLI çağrıldı (kısayol çalışmadı)"
    assert task_id and task_id.startswith("brain-")


def test_research_card_below_threshold_still_runs(board, tmp_path, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "brain_confidence_threshold", 0.40, raising=False)
    _brain(monkeypatch, 0.12)
    card = _card(board, id="kind-r2", title="Hibrit aramayı araştır",
                 goal="son gelişmeler", kind="research", provider="claude")
    board.apply_event(card.id, "task.assigned", payload={"agent": "arastirmaci"})

    bridge = _FakeBridge()
    board.run(card.id, bridge_factory=lambda p: bridge,
              agent_registry=_registry_with(tmp_path))
    assert bridge.calls, "eşiğin altındaki güvenle kart kapandı (yanlış kısayol)"


def test_write_card_runs_cli_with_brain_section(board, tmp_path, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "brain_confidence_threshold", 0.40, raising=False)
    _brain(monkeypatch, 0.95, "Damıtma için hazır bilgi.")
    card = _card(board, id="kind-w", title="Notları özetle",
                 goal="kısa rapor yaz", kind="write", provider="claude")
    board.apply_event(card.id, "task.assigned", payload={"agent": "arastirmaci"})

    bridge = _FakeBridge()
    board.run(card.id, bridge_factory=lambda p: bridge,
              agent_registry=_registry_with(tmp_path))
    assert bridge.calls, "write kartı için CLI çağrılmadı (kısayol uygulanmamalıydı)"
    prompt = str(bridge.calls[0].get("prompt") or "")
    assert "[BEYİN]" in prompt, "beyin paketi isteme girmedi"
    assert "Damıtma için hazır bilgi." in prompt


def test_entropy_checkpoint_is_written_under_board_root(board, tmp_path):
    """Entropy kartı Desk kökü altına DEĞİL `Entropy/Board/checkpoints`e yazar."""
    from entropy.core.paths import board_checkpoints_dir, desk_root

    card = _card(board, id="cp-entropy")
    res = board_tool_exec.execute(
        [_call("board_checkpoint", task_id=card.id, done="modül 1",
               next="modül 2", files=["a.py"], tests="pytest -q → 3 passed")],
        board=board, card=card, actor="arastirmaci", vault_path=tmp_path,
    )
    assert res[0]["ok"], res
    path = Path(res[0]["path"])
    assert path.is_file()
    assert path.parent == board_checkpoints_dir(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "modül 1" in text and "modül 2" in text
    root = desk_root(tmp_path)
    assert not root.exists() or not list(root.rglob("*.md")), \
        "Entropy kartı Desk kökü altına dosya yazdı"
