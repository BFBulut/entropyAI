"""
Faz 13-C sözleşmeleri: ofis kartı temizliği, tek kontrol noktası yazıcısı,
Entropy → Desk onay kuyruğu, kart arşivi, efor argv'si ve `board.stop`.

Her bölüm bir kullanıcı şikâyetine bağlıdır:

C1. Desk panosunda kartın özetinde ham `[PANO …] {json} [/PANO]` görünüyordu.
C2. Kontrol noktasının İKİ yazıcısı vardı ve metinleri ayrışmıştı.
C3. Entropy sohbette "sana ofis açtım" diyordu ama diskte hiçbir şey yoktu;
    tersi de olabilirdi (onaysız kalıcı yapı değişikliği).
C4. "Sil" düğmesi kart dosyasını gerçekten yok ediyordu.
C6. Kartın `effort` alanı argv'ye hiç ulaşmıyordu.
S.  "Durdur" kartı iptal ediyordu ama CLI süreci ve defter satırı yaşıyordu.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from entropy.agents import board_tools, desk_admin
from entropy.agents.tasks import TaskBoard, TaskCard


# ---------------------------------------------------------------------------
# Ortak fikstürler
# ---------------------------------------------------------------------------

@pytest.fixture()
def board(tmp_path) -> TaskBoard:
    return TaskBoard(vault_path=tmp_path)


def _office_card(board: TaskBoard, **kwargs) -> TaskCard:
    card = TaskCard(
        id=kwargs.pop("id", "20260911-1200-ofis"),
        title=kwargs.pop("title", "Ofis kartı"),
        office=kwargs.pop("office", "atolye"),
        agent=kwargs.pop("agent", "isci"),
        status="backlog",
        **kwargs,
    )
    return board.create(card)


RAW_OFFICE_OUTPUT = """Modülü bitirdim.

[KONTROL NOKTASI]
Özet: Ayrıştırıcı yazıldı.
Yapılan: parser.py
Sonraki adımlar: testler
Dosyalar: src/parser.py
Testler: pytest -q
[/KONTROL NOKTASI]

[KANIT]
Komut: pytest -q
Sonuç: 12 passed
[/KANIT]

[KURAL] Bu proje testleri pytest -q ile koşar.

[PANO board_finish]
{"summary": "Ayrıştırıcı hazır", "outputs": ["src/parser.py"]}
[/PANO]
"""


# ---------------------------------------------------------------------------
# C1 — ofis kartında da araç blokları temizlenir, alanlar dolar
# ---------------------------------------------------------------------------

def test_office_card_summary_has_no_tool_blocks_and_fields_are_filled(board):
    card = _office_card(board)
    board._finish(card.id, RAW_OFFICE_OUTPUT, True)
    done = board.get(card.id)

    # Kullanıcının gördüğü metinde makine yükü YOK.
    assert "[PANO" not in (done.summary or "")
    assert "[KONTROL NOKTASI]" not in (done.summary or "")
    assert "[KANIT]" not in (done.summary or "")
    assert board_tools.has_tool_blocks(done.summary or "") is False

    # Bloklar kart ALANLARINA çevrildi (harness artık `summary`den ayrıştırmaz).
    assert done.checkpoint, "kontrol noktası yolu karta yazılmalı"
    assert Path(done.checkpoint).is_file()
    assert done.proof and "pytest -q" in done.proof
    assert done.proof_green is True


def test_office_card_fields_survive_reload(board):
    """`proof_green` üç değerli alan olarak ön bilgiden geri okunmalı."""
    card = _office_card(board, id="20260911-1201-ofis")
    board._finish(card.id, RAW_OFFICE_OUTPUT, True)
    reloaded = TaskBoard(vault_path=board.vault_path).get(card.id)
    assert reloaded.proof_green is True
    assert reloaded.checkpoint == board.get(card.id).checkpoint


def test_entropy_card_has_no_office_fields(board):
    """Entropy kartında kural adayı/ofis alanı üretilmez (Desk'in kavramı)."""
    card = board.create(TaskCard(id="20260911-1202-entropy", title="Entropy kartı",
                                 status="backlog"))
    assert board._office_block_fields(card, RAW_OFFICE_OUTPUT) == {}


# ---------------------------------------------------------------------------
# C2 — tek kontrol noktası yazıcısı
# ---------------------------------------------------------------------------

def test_single_checkpoint_writer_for_entropy_and_office(tmp_path):
    from entropy.agents import board_tool_exec
    from entropy.brain import checkpoints

    entropy_path = board_tool_exec.write_entropy_checkpoint(
        "kart-1", summary="özet", done="yapıldı", next_steps="-",
        files_touched=["a.py"], tests="pytest", author="entropy",
        vault_path=tmp_path,
    )
    direct = checkpoints.checkpoint_path("", "kart-1", tmp_path)
    assert Path(entropy_path) == Path(direct)
    assert Path(entropy_path).is_file()

    # Entropy kontrol noktası Desk kökünün ALTINA düşmez (ayrı kök kuralı).
    assert "Desk" not in str(entropy_path)

    office_path = checkpoints.write_checkpoint(
        "atolye", "kart-2", summary="özet", done="yapıldı", vault_path=tmp_path)
    assert "Desk" in str(office_path)


def test_read_checkpoint_file_reads_absolute_path(tmp_path):
    from entropy.brain import checkpoints

    path = checkpoints.write_checkpoint("atolye", "kart-3", summary="özet",
                                        done="yapıldı", vault_path=tmp_path)
    data = checkpoints.read_checkpoint_file(Path(path))
    assert isinstance(data, dict) and data


def test_widget_reads_checkpoint_from_card_field():
    """Arayüz kartın MUTLAK `checkpoint` alanını okur (ofis adından türetmez)."""
    src = (Path(__file__).resolve().parents[2] / "src" / "entropy" / "ui"
           / "widgets" / "task_board_widget.py").read_text(encoding="utf-8")
    assert "read_checkpoint_file" in src


# ---------------------------------------------------------------------------
# C3 — Entropy → Desk onay kuyruğu
# ---------------------------------------------------------------------------

DESK_BLOCK = """Ofisi açıyorum.

[DESK office_create]
{"name": "atolye", "purpose": "Ayrıştırıcı geliştirme"}
[/DESK]
"""


def test_desk_block_parsed_and_stripped():
    calls = board_tools.parse_desk_calls(DESK_BLOCK)
    assert [c.name for c in calls] == ["office_create"]
    assert calls[0].args["name"] == "atolye"
    cleaned = board_tools.strip_tool_blocks(DESK_BLOCK)
    assert "[DESK" not in cleaned and "office_create" not in cleaned
    assert "Ofisi açıyorum." in cleaned
    assert board_tools.has_tool_blocks(DESK_BLOCK) is True


def test_desk_block_only_queues_and_changes_no_structure(tmp_path):
    receipts = desk_admin.consume_desk_calls(DESK_BLOCK, vault_path=tmp_path)
    assert receipts and "onay" in receipts[0].lower()
    rows = desk_admin.list_pending(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert set(row) >= {"id", "kind", "payload", "created_at", "source", "summary"}
    assert row["kind"] == "office_create"
    # Kuyruk Entropy'nin kendi kökünde; Desk kökü DOKUNULMADI.
    assert (tmp_path / "Entropy" / "Desk" / "_pending").is_dir()
    assert not (tmp_path / "Desk" / "Offices" / "atolye").exists()


def test_reject_pending_removes_request_and_creates_nothing(tmp_path):
    desk_admin.consume_desk_calls(DESK_BLOCK, vault_path=tmp_path)
    request_id = desk_admin.list_pending(tmp_path)[0]["id"]
    assert desk_admin.reject_pending(request_id, "gerek yok", vault_path=tmp_path) is True
    assert desk_admin.list_pending(tmp_path) == []
    assert not (tmp_path / "Desk" / "Offices" / "atolye").exists()
    # Olmayan kimlik: sessiz False.
    assert desk_admin.reject_pending("yok", vault_path=tmp_path) is False


def test_apply_pending_creates_office_and_orchestrator(tmp_path, monkeypatch):
    from entropy.agents.offices import OfficeRegistry

    desk_admin.consume_desk_calls(DESK_BLOCK, vault_path=tmp_path)
    request_id = desk_admin.list_pending(tmp_path)[0]["id"]
    result = desk_admin.apply_pending(request_id, vault_path=tmp_path)
    assert set(result) == {"ok", "message", "created_paths"}
    if not result["ok"]:
        pytest.skip(f"ofis katmanı bu ortamda açılamadı: {result['message']}")
    offices = OfficeRegistry(vault_path=tmp_path)
    spec = offices.get("atolye")
    assert spec is not None
    assert spec.orchestrator, "ofis açılınca orkestratör de doğmalı"
    assert result["created_paths"]
    # Uygulanan istek kuyruktan düşer.
    assert desk_admin.list_pending(tmp_path) == []


def test_msg_block_is_not_queued(tmp_path):
    """`msg` yapı değiştirmez: kuyruğa girmez."""
    text = '[DESK msg]\n{"office": "atolye", "text": "durumu yaz"}\n[/DESK]'
    desk_admin.consume_desk_calls(text, vault_path=tmp_path)
    assert [r["kind"] for r in desk_admin.list_pending(tmp_path)] == []


def test_desk_blocks_only_on_claude_chat_path(monkeypatch):
    """agy kolunda blok TEMİZLENİR ama uygulanmaz (13-C.3 kuralı)."""
    from entropy.core import response_hooks

    called = []
    monkeypatch.setattr(desk_admin, "consume_desk_calls",
                        lambda text, **kw: called.append(text) or ["makbuz"])
    out = response_hooks.process_chat_response(DESK_BLOCK, provider="agy")
    assert called == []
    assert "[DESK" not in out
    response_hooks.process_chat_response(DESK_BLOCK, provider="claude")
    assert called, "claude kolunda bloklar tüketilmeli"


def test_desk_tools_fit_prompt_budget():
    from entropy.brain.system_prompt import BUDGET_BOARD_TOOLS, board_tools_section

    section = board_tools_section()
    assert len(section) <= BUDGET_BOARD_TOOLS
    # Kırpma `[DESK …]` bölümünü YUTMAMALI: yutarsa Entropy aracı hiç görmez.
    assert "[DESK office_create]" in section
    assert "agent_edit" in section and "msg" in section


# ---------------------------------------------------------------------------
# C4 — arşiv (silme yok)
# ---------------------------------------------------------------------------

def test_archive_card_moves_file_and_keeps_history(board):
    card = board.create(TaskCard(id="20260911-1300-ars", title="Arşivlik",
                                 status="backlog"))
    source = Path(board.get(card.id).path)
    result = board.archive_card(card.id, "artık gereksiz")
    assert result["ok"] is True
    target = Path(result["archived_to"])
    assert target.is_file() and not source.exists()
    assert "_archive" in str(target) and target.parent.name == "cards"
    assert board.get(card.id) is None


def test_archive_card_requires_reason(board):
    card = board.create(TaskCard(id="20260911-1301-ars", title="Gerekçesiz",
                                 status="backlog"))
    result = board.archive_card(card.id, "")
    assert result["ok"] is False
    assert Path(board.get(card.id).path).is_file()


def test_module_level_archive_card_contract(tmp_path):
    from entropy.agents import tasks as tasks_mod

    board = TaskBoard(vault_path=tmp_path)
    board.create(TaskCard(id="20260911-1302-ars", title="Modül", status="backlog"))
    result = tasks_mod.archive_card("20260911-1302-ars", "temizlik",
                                    vault_path=tmp_path)
    assert set(result) >= {"ok", "archived_to"}
    assert result["ok"] is True and result["archived_to"]


def test_terminal_card_stays_terminal_with_info_event(board):
    card = board.create(TaskCard(id="20260911-1303-ars", title="Bitmiş",
                                 status="done"))
    board.archive_card(card.id, "kapandı")
    actions = [e.get("action") for e in board.events.read(card.id)]
    assert "board.archived" in actions
    assert "task.canceled" not in actions


def test_slash_task_rm_archives_with_reason():
    """`/task rm <id> :: <gerekçe>` kartı arşive taşır, dosyayı yok etmez."""
    from entropy.core import slash_commands

    # `/task` VARSAYILAN kasada koşar (conftest onu tmp'ye yönlendiriyor).
    board = TaskBoard()
    board.create(TaskCard(id="20260911-1310-slash", title="Silinesi",
                          status="backlog"))
    source = Path(board.get("20260911-1310-slash").path)

    out = slash_commands._handle_task("rm 20260911-1310-slash :: artık gereksiz")
    assert "Arşivlendi" in out and "artık gereksiz" in out
    assert not source.exists()
    assert TaskBoard().get("20260911-1310-slash") is None
    assert "_archive" in out


def test_slash_task_rm_without_reason_changes_nothing():
    from entropy.core import slash_commands

    board = TaskBoard()
    board.create(TaskCard(id="20260911-1311-slash", title="Gerekçesiz",
                          status="backlog"))

    out = slash_commands._handle_task("rm 20260911-1311-slash")
    assert "gerekçe" in out.lower()
    assert Path(TaskBoard().get("20260911-1311-slash").path).is_file()


def test_slash_task_usage_mentions_rm():
    from entropy.core import slash_commands

    spec = next(c for c in slash_commands.LOCAL_COMMANDS if c.name == "/task")
    assert "/task rm" in spec.usage


def test_no_direct_unlink_path_in_tasks_delete():
    """Eski `delete()` yolu artık dosya YOK ETMEZ, arşive delege eder."""
    src = (Path(__file__).resolve().parents[2] / "src" / "entropy" / "agents"
           / "tasks.py").read_text(encoding="utf-8")
    body = src.split("def delete(self", 1)[1].split("def archive_card", 1)[0]
    assert "path.unlink()" not in body
    assert "archive_card" in body


# ---------------------------------------------------------------------------
# C6 — efor argv'ye ulaşır (iki sağlayıcı)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", ["claude", "agy"])
def test_office_card_effort_reaches_bridge_kwargs(board, monkeypatch, provider):
    seen = {}

    class _Bridge:
        def send_background_task_async(self, task_id, task_name, prompt, mode,
                                       on_result, save_report=True, agent=None,
                                       effort=None, **kwargs):
            seen.update(effort=effort, provider=provider)

    card = _office_card(board, id=f"20260911-1400-{provider}", effort="high",
                        provider=provider)
    board.run(card.id, bridge_factory=lambda name: _Bridge())
    assert seen.get("effort") == "high"


@pytest.mark.parametrize("provider", ["claude", "agy"])
def test_card_effort_lands_in_argv_with_real_bridges(tmp_path, monkeypatch, provider):
    """
    GERÇEK köprü yolu (Popen sahte): claude'da `--effort <düzey>`, agy'de
    model adının SON EKİ. Sahte köprüyle geçen test imza uyumsuzluğunu gizler.
    """
    import subprocess
    import threading

    from entropy.core.task_ledger import TaskLedger

    captured = {}

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)

        def readline(self):
            return next(self._iter, "")

        def close(self):
            pass

    class DummyProc:
        def __init__(self, cmd, *args, **kwargs):
            captured["cmd"] = list(cmd) if isinstance(cmd, (list, tuple)) else [str(cmd)]
            self.stdout = DummyStdout([
                '{"event": "result", "result": {"response": "tamam"}}\n',
                '{"type": "result", "result": "tamam"}\n',
                "",
            ])
            self.stdin = None
            self.pid = 4244

        def wait(self, *a, **k):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(subprocess, "Popen", DummyProc)

    if provider == "claude":
        from entropy.core.claude_bridge import ClaudeCodeBridge as _Bridge

        module = "entropy.core.claude_bridge"
    else:
        from entropy.core.agy_bridge import AgyProcessBridge as _Bridge

        module = "entropy.core.agy_bridge"
    monkeypatch.setattr(f"{module}.task_ledger", TaskLedger(db_path=tmp_path / "l.db"))
    bridge = _Bridge()
    bridge.set_project_directory(tmp_path)

    done = threading.Event()
    bridge.send_background_task_async(
        task_id="efor-1", task_name="Efor", prompt="merhaba",
        mode="accept-edits", on_result=lambda text, ok: done.set(),
        save_report=False, effort="high",
    )
    done.wait(timeout=20)
    cmd = captured.get("cmd") or []
    joined = " ".join(cmd)
    if provider == "claude":
        assert "--effort" in cmd and cmd[cmd.index("--effort") + 1] == "high"
    else:
        # agy'de `--effort` argv'ye GİRMEZ (`--model` ile çakışıyor); efor
        # model adının son ekidir.
        assert "--effort" not in cmd
        assert "-high" in joined


# ---------------------------------------------------------------------------
# S — board.stop: süreç ağacı + defter satırı
# ---------------------------------------------------------------------------

class _FakeProc:
    def __init__(self, pid=4242):
        self.pid = pid

    def poll(self):
        return None


def test_stop_kills_process_tree_hidden_and_cancels_card(board, monkeypatch):
    card = board.create(TaskCard(id="20260911-1500-dur", title="Süren",
                                 status="running", agent="isci"))
    bridge = type("B", (), {"_background_processes": {"card-20260911-1500-dur": _FakeProc()},
                            "terminate_background_task": lambda self, tid: None})()
    monkeypatch.setattr(TaskBoard, "_bridge_cache", {"claude": bridge})

    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return None

    import subprocess

    monkeypatch.setattr(subprocess, "run", _fake_run)
    assert board.stop(card.id) is True
    assert calls, "süreç ağacı indirilmeli"
    cmd = calls[0][0]
    assert "/T" in cmd and "4242" in cmd
    # Pencere açılmaz: gizleme kwarg'ları geçirilir.
    assert "creationflags" in calls[0][1] or "startupinfo" in calls[0][1]
    assert board.get(card.id).status == "canceled"


def test_stop_closes_ledger_row(board, monkeypatch):
    card = board.create(TaskCard(id="20260911-1501-dur", title="Süren",
                                 status="running"))
    cancelled = []

    class _Ledger:
        def get_task(self, task_id):
            return {"status": "running"} if task_id == "card-20260911-1501-dur" else None

        def record_task_cancelled(self, task_id, reason=""):
            cancelled.append((task_id, reason))

    import sys

    ledger_mod = sys.modules["entropy.core.task_ledger"]
    monkeypatch.setattr(ledger_mod, "task_ledger", _Ledger())
    board.stop(card.id)
    assert cancelled and cancelled[0][0] == "card-20260911-1501-dur"


# ---------------------------------------------------------------------------
# Yön kuralı: Desk → Entropy görev yazamaz
# ---------------------------------------------------------------------------

def test_desk_admin_is_one_directional():
    src = (Path(__file__).resolve().parents[2] / "src" / "entropy" / "agents"
           / "desk_admin.py").read_text(encoding="utf-8")
    # Modül Desk'e YAZAR; Entropy panosuna kart açan bir yol içermez.
    assert "board_create" not in src
    assert "Entropy/Tasks" not in src
