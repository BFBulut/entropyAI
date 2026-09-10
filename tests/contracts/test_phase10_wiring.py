"""
FAZ 10-D — etkileşimli kartların kablolaması (harness ↔ pano ↔ köprü).

Doğrulanan kurallar:
  1. `interactive=True` YALNIZCA Desk ofis kartında geçilir; Entropy'nin kendi
     kartında geçilmez ve `config.desk_interactive_cards` kapalıyken hiç
     geçilmez. Kwarg'ı kabul etmeyen dar köprüye hiç gönderilmez.
  2. Takip turu kancaları: yazma kilidi meşgulse `on_followup_start` False
     döner (köprü mesajı göndermez) ve karta "kilit meşgul" hatası akar;
     alınabilirse sayaç artar, `on_followup_end` kilidi ve sayacı bırakır.
  3. Takip turu süren kart ofisin `max_parallel` bütçesinden yer tutar.
  4. `task_followup_completed` özeti kartın notlarına ve makbuzun
     `## İlerleme` bölümüne düşer.
  5. `resume_all` açılışta `worktrees.retry_orphans` çağırır; kalan yetim
     sayısı `office_status.orphan_worktrees` alanında görünür.
  6. `DeskRegistry.archive` ÖNCE kart worktree'lerini bırakır, canlı
     etkileşimli terminalleri kapatır, SONRA `archive_office` çağırır.

Hiçbir test gerçek agy/claude süreci başlatmaz.
"""

from dataclasses import replace

import pytest
from PySide6.QtCore import Qt

from entropy.agents import worktrees as wt
from entropy.agents.desk_registry import DeskOffice, DeskRegistry
from entropy.agents import harness as harness_module
from entropy.agents.harness import OfficeHarness
from entropy.agents.registry import AgentSpec
from entropy.agents.tasks import (
    TaskBoard,
    TaskCard,
    followup_note_line,
    new_task_id,
    record_followup,
)
from entropy.core.event_bus import bus
from entropy.core.project_lock import project_lock_manager


# ---------------------------------------------------------------------------
# Düzenek
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    from entropy.core.config import config

    vault = tmp_path / "Vault"
    (vault / "Entropy").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "obsidian_vault_path", vault, raising=False)
    monkeypatch.setattr(config, "desk_interactive_cards", True, raising=False)
    return vault


@pytest.fixture(autouse=True)
def clean_locks():
    project_lock_manager.reset()
    yield
    project_lock_manager.reset()


@pytest.fixture
def vault(tmp_path):
    return tmp_path / "Vault"


@pytest.fixture
def board(vault):
    return TaskBoard(vault_path=vault)


@pytest.fixture
def offices(vault):
    return DeskRegistry(vault_path=vault)


class RecordingBridge:
    """Çağrının anahtar argümanlarını saklayan sahte köprü."""

    provider_name = "agy"

    def __init__(self, autorun=False):
        self.calls = []
        self.autorun = autorun

    def send_background_task_async(self, task_id, task_name, prompt, **kw):
        self.calls.append(dict(kw, task_id=task_id))
        if self.autorun and kw.get("on_result"):
            kw["on_result"]("bitti", True)
        return task_id

    def terminate_background_task(self, task_id):
        return True


class NarrowBridge:
    """`interactive` kwarg'ını KABUL ETMEYEN eski sözleşme."""

    provider_name = "agy"

    def __init__(self):
        self.calls = []

    def send_background_task_async(self, task_id, task_name, prompt, mode=None,
                                   on_result=None, save_report=True, agent=None):
        self.calls.append(task_id)
        return task_id

    def terminate_background_task(self, task_id):
        return True


def make_office(offices, name="wiring-ofisi", max_parallel=2):
    offices.create(DeskOffice(
        name=name,
        purpose="Kablolama testi ofisi.",
        charter="# ofis\n\nKabul: kanıt göster.",
        max_parallel=max_parallel,
    ))
    agents = offices.agents(name)
    agents.update(AgentSpec(name="isci", role="worker", description="işçi",
                            provider="agy", tools_policy="read-write"))
    return offices.get(name)


def make_card(board, **kw):
    title = kw.pop("title", "Kart")
    data = dict(
        id=new_task_id(title), title=title, status="backlog", agent="",
        provider="agy", goal="Bir şey yap.", criteria=["ölçüt"],
    )
    data.update(kw)
    return board.create(TaskCard(**data))


# ---------------------------------------------------------------------------
# 1. interactive kwarg'ı yalnızca Desk kartında
# ---------------------------------------------------------------------------


def test_interactive_only_for_desk_office_cards(board, offices):
    make_office(offices)
    bridge = RecordingBridge()
    factory = lambda provider: bridge  # noqa: E731

    # Faz 11-C durum makinesi: ajansız `backlog` kart koşmaz (backlog→running
    # geçişi yok). Entropy kartı bu yüzden Entropy kadrosundaki bir ajana atanır.
    from entropy.agents.registry import AgentRegistry

    AgentRegistry(vault_path=board.vault_path).update(AgentSpec(
        name="entropy-isci", role="worker", description="işçi",
        provider="agy", tools_policy="read-only",
    ))
    entropy_card = make_card(board, title="Entropy kartı", agent="entropy-isci")
    board.run(entropy_card.id, bridge_factory=factory)
    assert bridge.calls[-1].get("interactive") is None

    desk_card = make_card(board, title="Ofis kartı", office="wiring-ofisi",
                          agent="isci")
    board.run(desk_card.id, bridge_factory=factory,
              agent_registry=offices.agents("wiring-ofisi"))
    assert bridge.calls[-1].get("interactive") is True


def test_interactive_off_when_flag_disabled(board, offices, monkeypatch):
    from entropy.core.config import config

    monkeypatch.setattr(config, "desk_interactive_cards", False, raising=False)
    make_office(offices)
    bridge = RecordingBridge()
    card = make_card(board, title="Ofis kartı", office="wiring-ofisi", agent="isci")
    board.run(card.id, bridge_factory=lambda p: bridge,
              agent_registry=offices.agents("wiring-ofisi"))
    assert bridge.calls[-1].get("interactive") is None


def test_narrow_bridge_never_sees_interactive_kwarg(board, offices):
    make_office(offices)
    bridge = NarrowBridge()
    card = make_card(board, title="Ofis kartı", office="wiring-ofisi", agent="isci")
    assert board.run(card.id, bridge_factory=lambda p: bridge,
                     agent_registry=offices.agents("wiring-ofisi"))
    assert bridge.calls  # TypeError ile düşmedi


# ---------------------------------------------------------------------------
# 2. Kilit kancaları
# ---------------------------------------------------------------------------


def _harness(offices, board, name="wiring-ofisi"):
    return OfficeHarness(name, board=board, offices=offices,
                         registry=offices.agents(name))


def test_followup_start_reacquires_write_lock_and_counts(board, offices, tmp_path):
    make_office(offices)
    harness = _harness(offices, board)
    project = str(tmp_path / "proje")
    start, end = harness._followup_hooks("kart-1", project, needs_write=True)

    assert start("card-kart-1") is True
    assert "kart-1" in harness._followup_active
    assert project_lock_manager.is_write_locked(project)

    end("card-kart-1")
    assert "kart-1" not in harness._followup_active
    assert not project_lock_manager.is_write_locked(project)


def test_followup_start_returns_false_when_lock_busy(board, offices, tmp_path):
    make_office(offices)
    harness = _harness(offices, board)
    project = str(tmp_path / "proje")
    # Kilit BAŞKA bir iş parçacığında tutulur: `core.project_lock` aynı iş
    # parçacığında yeniden girişlidir, aynı yerden alınsa çakışma görünmezdi.
    other = harness_module.WriteLockHolder(project)
    assert other.acquire(timeout=2.0)

    events = []
    bus.agent_stream.connect(events.append)
    try:
        start, _end = harness._followup_hooks("kart-1", project, needs_write=True)
        assert start("card-kart-1") is False
    finally:
        bus.agent_stream.disconnect(events.append)
        other.release()

    assert "kart-1" not in harness._followup_active
    assert any(e.get("kind") == "error" and "kilid" in (e.get("text") or "").lower()
               for e in events)


def test_read_intent_followup_takes_no_lock_but_counts(board, offices, tmp_path):
    make_office(offices)
    harness = _harness(offices, board)
    project = str(tmp_path / "proje")
    start, end = harness._followup_hooks("kart-2", project, needs_write=False)
    assert start("card-kart-2") is True
    assert not project_lock_manager.is_write_locked(project)
    assert "kart-2" in harness._followup_active
    end("card-kart-2")
    assert "kart-2" not in harness._followup_active


def test_followup_holder_consumes_parallel_slot(board, offices):
    office = make_office(offices, max_parallel=1)
    assert office.max_parallel == 1
    harness = _harness(offices, board)
    parent = make_card(board, title="Üst", office=office.name, status="running")
    kids = [
        make_card(board, title=f"Alt {i}", office=office.name, agent="isci",
                  parent=parent.id)
        for i in range(2)
    ]
    board.update(replace(parent, children=[k.id for k in kids]))

    bridge = RecordingBridge()
    harness.bridge_factory = lambda p: bridge
    harness._followup_active.add(kids[0].id)
    harness._pump(parent.id)
    # Tek kapasite takip turundaki kart tarafından tutuluyor: yeni kart yok.
    assert bridge.calls == []

    harness._followup_active.clear()
    harness._pump(parent.id)
    assert len(bridge.calls) == 1


# ---------------------------------------------------------------------------
# 3. Takip turu özeti
# ---------------------------------------------------------------------------


def test_followup_summary_lands_in_notes_and_receipt(board, offices, vault):
    office = make_office(offices)
    harness = _harness(offices, board)
    parent = make_card(board, title="Üst", office=office.name, status="running")
    child = make_card(board, title="Alt", office=office.name, agent="isci",
                      parent=parent.id, status="done")
    board.update(replace(parent, children=[child.id]))

    payload = {
        "task_id": f"card-{child.id}",
        "card_id": child.id,
        "text": "İkinci turda testler yeşil.",
        "usage": {"total_tokens": 1234},
        "turn": 2,
        "success": True,
    }
    assert record_followup(payload, vault_path=vault) is True
    # İkinci kez yazılmaz (aynı satır).
    assert record_followup(payload, vault_path=vault) is False

    line = followup_note_line(payload)
    assert line in (board.get(child.id).notes or "")

    body = harness._receipt_body(board.get(parent.id), [board.get(child.id)])
    assert "## İlerleme" in body
    assert "Takip turu 2" in body
    assert "1234 token" in body


def test_record_followup_ignores_unknown_card(vault):
    assert record_followup({"card_id": "yok-boyle-kart"}, vault_path=vault) is False


# ---------------------------------------------------------------------------
# 4. resume_all → retry_orphans, office_status → orphan_worktrees
# ---------------------------------------------------------------------------


def test_resume_all_retries_orphan_worktrees(board, offices, monkeypatch):
    make_office(offices)
    seen = []

    def _spy(vault_path=None):
        seen.append(vault_path)
        return {"cleared": ["a"], "remaining": []}

    monkeypatch.setattr(wt, "retry_orphans", _spy)
    OfficeHarness.resume_all(board=board, offices=offices)
    assert seen and str(seen[0]) == str(offices.vault_path)


def test_office_status_reports_orphan_count(board, offices, monkeypatch):
    from entropy.agents import mailbox

    office = make_office(offices)
    monkeypatch.setattr(
        wt, "list_orphans",
        lambda repo=None, vault_path=None: [{"path": "x"}, {"path": "y"}],
    )
    status = mailbox.office_status(office.name, vault_path=offices.vault_path)
    assert status["orphan_worktrees"] == 2


# ---------------------------------------------------------------------------
# 5. Arşivde worktree serbest bırakma
# ---------------------------------------------------------------------------


def test_archive_releases_worktrees_before_archiving(board, offices, monkeypatch):
    office = make_office(offices)
    card = make_card(board, title="Alt", office=office.name, agent="isci",
                     worktree=r"C:\tmp\wt-1", branch="desk/alt")

    order = []
    monkeypatch.setattr(
        wt, "release_worktree",
        lambda c, force=True, vault_path=None: order.append(("wt", c.id)) or {"removed": True},
    )
    from entropy.memory import vault_hygiene

    monkeypatch.setattr(
        vault_hygiene, "archive_office",
        lambda name, vault_path=None, dry_run=True, date=None:
            order.append(("archive", name)) or {"office": name},
    )

    class _Bridge:
        def __init__(self):
            self.closed = []

        def interactive_task_ids(self):
            return [f"card-{card.id}", "card-baska-ofis"]

        def close_interactive(self, task_id, reason=""):
            self.closed.append(task_id)
            return True

    bridge = _Bridge()
    TaskBoard._bridge_cache["agy"] = bridge
    try:
        out = offices.archive(office.name)
    finally:
        TaskBoard._bridge_cache.pop("agy", None)

    assert order == [("wt", card.id), ("archive", office.name)]
    assert out["worktrees"] == [card.worktree]
    # Yalnızca BU ofisin kartının terminali kapanır.
    assert bridge.closed == [f"card-{card.id}"]


def test_archive_dry_run_touches_nothing(board, offices, monkeypatch):
    office = make_office(offices)
    make_card(board, title="Alt", office=office.name, agent="isci",
              worktree=r"C:\tmp\wt-2")
    calls = []
    monkeypatch.setattr(
        wt, "release_worktree",
        lambda c, force=True, vault_path=None: calls.append(c.id),
    )
    offices.archive(office.name, dry_run=True)
    assert calls == []


# ---------------------------------------------------------------------------
# 6. GERÇEK köprü yolu (Popen taklidi) — sahte köprüyle geçen test yetmez
# ---------------------------------------------------------------------------


class _RealStdout:
    def __init__(self, q):
        self._q = q
        self.closed = False

    def readline(self):
        import queue as _q

        try:
            item = self._q.get(timeout=5.0)
        except _q.Empty:
            return ""
        return "" if item is None else item

    def close(self):
        self.closed = True


class _RealStdin:
    def __init__(self, proc):
        self._proc = proc
        self.written = []
        self.closed = False

    def write(self, payload):
        if self.closed:
            raise ValueError("stdin kapalı")
        self.written.append(payload)
        self._proc.feed_next_turn()

    def flush(self):
        pass

    def close(self):
        if self.closed:
            return
        self.closed = True
        self._proc.finish()


class _RealProc:
    """agy taklidi: stdin'e her yazımda sıradaki turun satırlarını basar."""

    instances = []
    turns = []

    def __init__(self, *args, **kwargs):
        import queue as _q

        self.pid = 4321
        self._queue = _q.Queue()
        self._turns = [list(t) for t in type(self).turns]
        self._index = 0
        self.stdout = _RealStdout(self._queue)
        self.stdin = _RealStdin(self)
        self._done = __import__("threading").Event()
        type(self).instances.append(self)

    def feed_next_turn(self):
        if self._index >= len(self._turns):
            return
        for line in self._turns[self._index]:
            self._queue.put(line)
        self._index += 1

    def finish(self):
        self._done.set()
        self._queue.put(None)

    def poll(self):
        return 0 if self._done.is_set() else None

    def wait(self, timeout=None):
        self._done.wait(timeout if timeout is not None else 5.0)
        return 0

    def terminate(self):
        self.finish()

    def kill(self):
        self.finish()


def _turn(text, total):
    return [
        '{"event": "result", "result": {"response": "%s", '
        '"usage": {"input_tokens": %d, "output_tokens": 10, "total_tokens": %d}}}\n'
        % (text, total - 10, total)
    ]


def _wait(pred, timeout=10.0):
    import time

    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def test_real_bridge_desk_card_followup_takes_lock_and_writes_note(
        board, offices, tmp_path, monkeypatch, vault):
    """
    Uçtan uca: gerçek `AgyProcessBridge` + sahte Popen.

    Doğrulanan: (1) kart ilk turda finalize olur ve köprü proje kilidini
    BIRAKIR, (2) takip mesajı harness kancasını çağırır ve kilit yeniden
    alınır, (3) tur bitince kilit + sayaç bırakılır, (4) `task_followup_completed`
    kartın notlarına düşer.
    """
    import entropy.memory.obsidian.vault_manager as vm_mod
    from entropy.core.agy_bridge import AgyProcessBridge
    from entropy.core.task_ledger import TaskLedger

    monkeypatch.setattr("subprocess.run", lambda *a, **k: None)
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger",
                        TaskLedger(db_path=tmp_path / "ledger.db"))
    monkeypatch.setattr(vm_mod.ObsidianVaultManager, "save_research_report",
                        lambda self, *a, **k: tmp_path / "rapor.md")
    _RealProc.instances = []
    _RealProc.turns = [_turn("birinci tur", 120), _turn("ikinci tur", 205)]
    monkeypatch.setattr("subprocess.Popen", _RealProc)

    office = make_office(offices)
    harness = _harness(offices, board)
    card = make_card(board, title="Yazma kartı", office=office.name, agent="isci",
                     goal="Kodu düzelt ve testleri yaz.", intent="write")
    project = str(tmp_path / "proje")

    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)
    start_hook, end_hook = harness._followup_hooks(card.id, project, needs_write=True)

    followed = []
    bus.task_followup_completed.connect(followed.append, Qt.DirectConnection)
    try:
        task_id = board.run(
            card.id,
            bridge_factory=lambda p: bridge,
            agent_registry=offices.agents(office.name),
            project_path=project,
            interactive=True,
            on_followup_start=start_hook,
            on_followup_end=end_hook,
        )
        assert task_id == f"card-{card.id}"
        # 1. tur: kart kapanır ama süreç canlı kalır.
        assert _wait(lambda: board.get(card.id).status in ("review", "done", "failed"))
        assert _wait(lambda: task_id in bridge.interactive_task_ids())
        # Köprü ilk finalize'da kilidi bıraktı: kanca onu YENİDEN alabilmeli.
        assert _wait(lambda: not project_lock_manager.is_write_locked(project))

        assert bridge.send_followup(task_id, "ikinci turu koş") is True
        assert _wait(lambda: len(followed) >= 1)
    finally:
        bus.task_followup_completed.disconnect(followed.append)
        bridge.close_interactive(task_id)
        harness.release_followup(card.id)

    payload = followed[0]
    assert payload["card_id"] == card.id and payload["turn"] == 1
    # Tur bittiğinde kilit ve sayaç bırakıldı.
    assert _wait(lambda: card.id not in harness._followup_active)
    assert record_followup(payload, vault_path=vault) is True
    assert "Takip turu 1" in (board.get(card.id).notes or "")


# ----------------------------------------------------- 7) gercek ofis arsivlenir

def test_archive_office_moves_a_real_office_folder(tmp_path):
    """
    Kunyesi (`OFFICE.md`) olan GERCEK bir ofis arsive TASINIR.

    Olculdu (Faz 10-C, canli kosu): `archive_stale` icindeki "artik gercek
    ofis" guard'i kosulsuz calistigi icin `DeskRegistry.archive("dogrulama-10")`
    hicbir sey tasimiyor, `count=0` ve `skipped=[artik_gercek_ofis]` donuyordu;
    Desk'teki "Arsivle" dugmesi de sessizce etkisizdi. Guard artik yalnizca
    hayalet ofis taramasinda gecerli (`intentional=False`).
    """
    from entropy.memory.vault_hygiene import archive_office

    office_dir = tmp_path / "Desk" / "Offices" / "gercek"
    (office_dir / "cards").mkdir(parents=True)
    (office_dir / "OFFICE.md").write_text("---\nname: gercek\n---\n", encoding="utf-8")
    (office_dir / "MEMORY.md").write_text("ofis bellegi", encoding="utf-8")

    out = archive_office("gercek", vault_path=tmp_path, dry_run=False)

    assert out["count"] == 1, out
    assert out["folder"]["skipped"] == []
    assert not office_dir.exists()
    archived = list((tmp_path / "Entropy" / "_archive").rglob("MEMORY.md"))
    assert archived, "ofis klasoru arsivde bulunamadi"


def test_ghost_office_guard_still_protects_real_offices(tmp_path):
    """Hayalet tarama yolu (`intentional` yok) kunyeli ofise HALA dokunmaz."""
    from entropy.memory.vault_hygiene import archive_stale

    office_dir = tmp_path / "Desk" / "Offices" / "gercek"
    office_dir.mkdir(parents=True)
    (office_dir / "OFFICE.md").write_text("---\nname: gercek\n---\n", encoding="utf-8")

    out = archive_stale([str(office_dir)], vault_path=tmp_path, dry_run=False)

    assert out["count"] == 0
    assert out["skipped"] == [{"path": str(office_dir), "reason": "artik_gercek_ofis"}]
    assert office_dir.exists()
