"""Comprehensive tests for TaskLedger and ProjectLockManager and their bridge integration."""

import threading
import time
from pathlib import Path
import pytest

from entropy.core.task_ledger import TaskLedger, TaskStatus
from entropy.core.project_lock import ProjectLockManager, _ProjectRWLock
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.event_bus import bus


# =====================================================================
# 1. TaskLedger Tests
# =====================================================================

def test_task_ledger_crud_and_transitions(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    ledger = TaskLedger(db_path=db_file)

    task_id = "task-001"
    task_name = "Codebase Refactor"
    project_path = str(tmp_path / "project_a")

    # 1. Record task start
    ledger.record_task_start(task_id, task_name, project_path)
    task = ledger.get_task(task_id)

    assert task is not None
    assert task["task_id"] == task_id
    assert task["task_name"] == task_name
    assert task["project_path"] == project_path
    assert task["status"] == TaskStatus.RUNNING.value
    assert task["created_at"] is not None
    assert task["started_at"] is not None
    assert task["completed_at"] is None
    assert task["error"] is None

    # 2. Record success
    summary_text = "Refactored 5 modules successfully"
    ledger.record_task_success(task_id, summary=summary_text)
    task = ledger.get_task(task_id)

    assert task["status"] == TaskStatus.SUCCESS.value
    assert task["completed_at"] is not None
    assert task["result_summary"] == summary_text

    # 3. Test failure transition on another task
    fail_task_id = "task-002"
    ledger.record_task_start(fail_task_id, "Failing Job", project_path)
    ledger.record_task_failure(fail_task_id, error="Process crashed with exit code 1")
    failed_task = ledger.get_task(fail_task_id)

    assert failed_task["status"] == TaskStatus.FAILED.value
    assert failed_task["completed_at"] is not None
    assert "Process crashed" in failed_task["error"]


def test_task_ledger_pending_and_cancelled(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    ledger = TaskLedger(db_path=db_file)

    task_id = "task-pending-01"
    ledger.record_task_pending(task_id, "Scheduled Job", str(tmp_path))
    task = ledger.get_task(task_id)
    assert task["status"] == TaskStatus.PENDING.value
    assert task["started_at"] is None

    # Transition from PENDING to RUNNING
    ledger.record_task_start(task_id, "Scheduled Job (Running)", str(tmp_path))
    task = ledger.get_task(task_id)
    assert task["status"] == TaskStatus.RUNNING.value
    assert task["started_at"] is not None

    # Cancel task
    ledger.record_task_cancelled(task_id, reason="Cancelled by user")
    task = ledger.get_task(task_id)
    assert task["status"] == TaskStatus.CANCELLED.value
    assert task["error"] == "Cancelled by user"


def test_task_ledger_list_and_active_queries(tmp_path):
    db_file = tmp_path / "test_tasks.db"
    ledger = TaskLedger(db_path=db_file)

    for i in range(10):
        t_id = f"t-{i:02d}"
        ledger.record_task_start(t_id, f"Job {i}", str(tmp_path))
        if i < 4:
            ledger.record_task_success(t_id, summary=f"Done {i}")
        elif i < 7:
            ledger.record_task_failure(t_id, error=f"Err {i}")
        # remaining 3 are still RUNNING

    recent = ledger.list_recent_tasks(limit=5)
    assert len(recent) == 5

    active = ledger.get_active_tasks()
    assert len(active) == 3
    for a in active:
        assert a["status"] in [TaskStatus.RUNNING.value, TaskStatus.PENDING.value]


def test_task_ledger_concurrent_writes(tmp_path):
    db_file = tmp_path / "test_concurrent.db"
    ledger = TaskLedger(db_path=db_file)

    num_threads = 15
    errors = []

    def worker(idx: int):
        try:
            tid = f"thread-task-{idx}"
            ledger.record_task_start(tid, f"Concurrent Worker {idx}", str(tmp_path))
            time.sleep(0.01)
            if idx % 2 == 0:
                ledger.record_task_success(tid, summary=f"Success from {idx}")
            else:
                ledger.record_task_failure(tid, error=f"Failure from {idx}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    recent = ledger.list_recent_tasks(limit=100)
    assert len(recent) == num_threads


def test_task_ledger_persistence_recovery(tmp_path):
    db_file = tmp_path / "test_persist.db"
    ledger1 = TaskLedger(db_path=db_file)
    ledger1.record_task_start("persist-1", "Persist Job", str(tmp_path))
    ledger1.record_task_success("persist-1", "Saved to SQLite disk")

    # Reopen ledger using a fresh instance pointing to same file
    ledger2 = TaskLedger(db_path=db_file)
    task = ledger2.get_task("persist-1")
    assert task is not None
    assert task["status"] == TaskStatus.SUCCESS.value
    assert task["result_summary"] == "Saved to SQLite disk"


# =====================================================================
# 2. ProjectLockManager Tests
# =====================================================================

def test_project_lock_exclusive_write():
    mgr = ProjectLockManager()
    project_path = "C:/TestProject/Alpha"

    # Thread 1 acquires write lock
    assert mgr.acquire_write(project_path, timeout=1.0) is True
    assert mgr.is_write_locked(project_path) is True
    assert mgr.is_locked(project_path) is True

    # Thread 2 tries to acquire write lock with short timeout -> should fail
    thread2_acquired = []

    def t2_runner():
        acq = mgr.acquire_write(project_path, timeout=0.05)
        thread2_acquired.append(acq)

    t2 = threading.Thread(target=t2_runner)
    t2.start()
    t2.join()

    assert thread2_acquired == [False]

    # Thread 1 releases write lock
    mgr.release_write(project_path)
    assert mgr.is_write_locked(project_path) is False
    assert mgr.is_locked(project_path) is False


def test_project_lock_shared_reads():
    mgr = ProjectLockManager()
    project_path = "C:/TestProject/Beta"

    acquired_reads = []

    def reader_worker(idx: int):
        acq = mgr.acquire_read(project_path, timeout=1.0)
        acquired_reads.append((idx, acq))
        time.sleep(0.05)
        mgr.release_read(project_path)

    threads = [threading.Thread(target=reader_worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(acquired_reads) == 3
    assert all(acq is True for _, acq in acquired_reads)
    assert mgr.is_locked(project_path) is False


def test_project_lock_mutual_exclusion():
    mgr = ProjectLockManager()
    project_path = "C:/TestProject/Gamma"

    # Acquire shared read lock in main thread
    assert mgr.acquire_read(project_path, timeout=1.0) is True

    # Background thread tries to acquire write lock -> must fail while read is held
    writer_result = []

    def write_worker():
        acq = mgr.acquire_write(project_path, timeout=0.05)
        writer_result.append(acq)

    w_thread = threading.Thread(target=write_worker)
    w_thread.start()
    w_thread.join()

    assert writer_result == [False]

    # Release read lock
    mgr.release_read(project_path)

    # Now writer can acquire
    assert mgr.acquire_write(project_path, timeout=1.0) is True
    mgr.release_write(project_path)


def test_project_lock_reentrancy():
    mgr = ProjectLockManager()
    project_path = "C:/TestProject/Delta"

    # Re-entrant write lock on same thread
    assert mgr.acquire_write(project_path, timeout=1.0) is True
    assert mgr.acquire_write(project_path, timeout=1.0) is True
    assert mgr.is_write_locked(project_path) is True

    # Release once -> should still be write-locked
    mgr.release_write(project_path)
    assert mgr.is_write_locked(project_path) is True

    # Release twice -> fully released
    mgr.release_write(project_path)
    assert mgr.is_write_locked(project_path) is False

    # Re-entrant read lock on same thread
    assert mgr.acquire_read(project_path, timeout=1.0) is True
    assert mgr.acquire_read(project_path, timeout=1.0) is True
    mgr.release_read(project_path)
    mgr.release_read(project_path)
    assert mgr.is_locked(project_path) is False


def test_project_lock_context_managers():
    mgr = ProjectLockManager()
    project_path = "C:/TestProject/Epsilon"

    # Test write_lock context manager and exception safety
    with pytest.raises(ValueError):
        with mgr.write_lock(project_path):
            assert mgr.is_write_locked(project_path) is True
            raise ValueError("Deliberate error inside write lock")

    # Lock must be released even after exception
    assert mgr.is_write_locked(project_path) is False

    # Test read_lock context manager
    with mgr.read_lock(project_path):
        assert mgr.is_locked(project_path) is True
        assert mgr.is_write_locked(project_path) is False

    assert mgr.is_locked(project_path) is False


def test_project_lock_context_manager_timeout():
    mgr = ProjectLockManager()
    project_path = "C:/TestProject/Zeta"

    assert mgr.acquire_write(project_path, timeout=1.0) is True

    # Attempt to use write_lock context manager from another thread
    error_raised = []

    def other_thread():
        try:
            with mgr.write_lock(project_path, timeout=0.05):
                pass
        except TimeoutError as e:
            error_raised.append(e)

    t = threading.Thread(target=other_thread)
    t.start()
    t.join()

    assert len(error_raised) == 1
    assert isinstance(error_raised[0], TimeoutError)

    mgr.release_write(project_path)


def test_project_lock_path_normalization(tmp_path):
    mgr = ProjectLockManager()
    p1 = tmp_path / "alpha"
    p1.mkdir()
    p2 = tmp_path / "alpha" / "."

    assert mgr.acquire_write(p1, timeout=1.0) is True
    # p2 resolves to same folder, so write lock on p2 from another thread must time out
    timed_out = []

    def try_p2():
        acq = mgr.acquire_write(p2, timeout=0.05)
        timed_out.append(acq)

    t = threading.Thread(target=try_p2)
    t.start()
    t.join()

    assert timed_out == [False]
    mgr.release_write(p1)


# =====================================================================
# 3. Bridge Integration Tests
# =====================================================================

def test_bridge_code_modifying_intent_detection():
    bridge = AgyProcessBridge()

    # Modifying intents (Turkish and English)
    modifying_prompts = [
        "src/entropy/core/task_ledger.py dosyas\u0131n\u0131 g\u00fcncelle",
        "Yeni bir test dosyas\u0131 olu\u015ftur ve fonksiyonlar\u0131 ekle",
        "Kod taban\u0131ndaki hatalar\u0131 d\u00fczelt ve refactor et",
        "README.md dosyas\u0131n\u0131 de\u011fi\u015ftir",
        "/edit main.py",
        "Write a new class in database.py",
        "Create a script to parse logs",
        "Update the dependencies in pyproject.toml",
    ]
    for prompt in modifying_prompts:
        assert bridge.is_code_modifying_intent(prompt) is True, f"Failed for: {prompt}"

    # Non-modifying conversational prompts
    conversational_prompts = [
        "Merhaba, nas\u0131ls\u0131n?",
        "Bu projenin mimarisi nedir?",
        "Obsidian haf\u0131zas\u0131ndaki en son notlar\u0131 oku",
        "Sistemdeki aktif modelleri listele",
        "Explain how the reader-writer lock works",
        "What is the current time?",
    ]
    for prompt in conversational_prompts:
        assert bridge.is_code_modifying_intent(prompt) is False, f"Failed for: {prompt}"

    # Explicit mode overrides
    assert bridge.is_code_modifying_intent("Sadece oku", mode="code") is True
    assert bridge.is_code_modifying_intent("Dosyay\u0131 g\u00fcncelle", mode="plan") is False


def test_bridge_background_task_ledger_and_lock_integration(tmp_path, monkeypatch):
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    from entropy.core.task_ledger import task_ledger
    from entropy.core.project_lock import project_lock_manager

    # Override ledger with temporary database
    test_ledger = TaskLedger(db_path=tmp_path / "bridge_ledger.db")
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", test_ledger)

    task_id = "test-bg-task-42"
    task_name = "Automated Security Audit"

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)
        def readline(self):
            return next(self._iter, "")
        def close(self):
            pass

    class DummyProc:
        def __init__(self, *args, **kwargs):
            self.stdout = DummyStdout([
                '{"event": "step_update", "step_update": {"text_delta": "Audit complete"}}\n',
                '{"event": "result", "result": {"response": "All clear, no vulnerabilities"}}\n',
                ""
            ])
            self.pid = 4242
        def wait(self):
            return 0
        def poll(self):
            return 0  # surec bitti

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    # Execute synchronous worker logic
    bridge._execute_background_task_worker(
        task_id=task_id,
        task_name=task_name,
        prompt="Audit the codebase for security flaws",
        mode="accept-edits"
    )

    # 1. Verify ledger state
    task_record = test_ledger.get_task(task_id)
    assert task_record is not None
    assert task_record["status"] == TaskStatus.SUCCESS.value
    assert task_record["task_name"] == task_name
    assert "Audit complete" in task_record["result_summary"]

    # 2. Verify lock was fully released
    assert project_lock_manager.is_write_locked(tmp_path) is False
    assert project_lock_manager.is_locked(tmp_path) is False


def test_bridge_background_task_failure_recording(tmp_path, monkeypatch):
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    test_ledger = TaskLedger(db_path=tmp_path / "bridge_fail_ledger.db")
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", test_ledger)

    from entropy.core.project_lock import project_lock_manager

    task_id = "test-fail-task-99"
    task_name = "Failing Autonomous Job"

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)
        def readline(self):
            return next(self._iter, "")
        def close(self):
            pass

    class FailingProc:
        def __init__(self, *args, **kwargs):
            self.stdout = DummyStdout(['Error encountered\n', ''])
        def wait(self):
            return 1  # Non-zero exit code
        def poll(self):
            return 1  # surec bitti

    monkeypatch.setattr("subprocess.Popen", FailingProc)

    bridge._execute_background_task_worker(
        task_id=task_id,
        task_name=task_name,
        prompt="This job will fail",
        mode="accept-edits"
    )

    task_record = test_ledger.get_task(task_id)
    assert task_record is not None
    assert task_record["status"] == TaskStatus.FAILED.value
    assert task_record["error"] is not None

    # Verify lock released
    assert project_lock_manager.is_write_locked(tmp_path) is False


def test_prompt_worker_lock_timeout_handling(tmp_path, monkeypatch):
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    from entropy.core.project_lock import project_lock_manager

    # 1. Simulate an active background task holding write lock
    assert project_lock_manager.acquire_write(tmp_path, timeout=1.0) is True

    terminal_outputs = []
    bus.terminal_output_received.connect(lambda msg: terminal_outputs.append(msg))

    # Mock acquire_write with immediate timeout inside _execute_prompt_worker for test speed
    original_acquire_write = project_lock_manager.acquire_write
    monkeypatch.setattr(
        project_lock_manager,
        "acquire_write",
        lambda path, timeout=None: False
    )

    bridge._execute_prompt_worker("Yeni bir dosya oluştur", mode="accept-edits")

    # Verify notice and timeout message were emitted to terminal
    combined_output = "".join(terminal_outputs)
    assert "[Proje Kilidi: Arka plan görevi çalışıyor, işlem bekleniyor...]" in combined_output
    assert "[Proje Kilidi: Zaman aşımı! Arka plan görevi projeyi kullanıyor." in combined_output

    # Clean up background write lock
    project_lock_manager.release_write(tmp_path)
    assert project_lock_manager.is_write_locked(tmp_path) is False


def test_prompt_worker_normal_read_lock_and_release(tmp_path, monkeypatch):
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    from entropy.core.project_lock import project_lock_manager

    class DummyStdout:
        def __init__(self, lines):
            self._iter = iter(lines)
        def readline(self):
            return next(self._iter, "")
        def close(self):
            pass

    class DummyProc:
        def __init__(self, *args, **kwargs):
            self.stdout = DummyStdout(['{"event": "result", "result": {"response": "Hello"}}\n', ''])
            self.pid = 9999
        def wait(self):
            return 0
        def poll(self):
            return 0  # surec bitti

    monkeypatch.setattr("subprocess.Popen", DummyProc)

    # Conversational query -> acquires read lock
    bridge._execute_prompt_worker("Merhaba, bu proje nedir?", mode="accept-edits")

    # In finally block, lock must be 100% released
    assert project_lock_manager.is_locked(tmp_path) is False
    assert project_lock_manager.is_write_locked(tmp_path) is False


def test_task_ledger_restart_clears_old_errors(tmp_path):
    db_file = tmp_path / "test_restart.db"
    ledger = TaskLedger(db_path=db_file)

    task_id = "restart-001"
    # 1. First run fails
    ledger.record_task_start(task_id, "Flaky Task", str(tmp_path))
    ledger.record_task_failure(task_id, error="Network timeout 504")

    task = ledger.get_task(task_id)
    assert task["status"] == TaskStatus.FAILED.value
    assert task["error"] == "Network timeout 504"
    assert task["completed_at"] is not None

    # 2. Restart task -> status should be RUNNING, and old error/completed_at must be cleared
    ledger.record_task_start(task_id, "Flaky Task (Retry)", str(tmp_path))
    task_after = ledger.get_task(task_id)
    assert task_after["status"] == TaskStatus.RUNNING.value
    assert task_after["error"] is None
    assert task_after["completed_at"] is None
    assert task_after["result_summary"] is None


def test_task_ledger_connection_is_closed(tmp_path):
    db_file = tmp_path / "test_conn_close.db"
    ledger = TaskLedger(db_path=db_file)

    # Calling methods opens and closes connections cleanly
    ledger.record_task_start("t-conn", "Conn Task", str(tmp_path))
    ledger.record_task_success("t-conn", "Finished")
    _ = ledger.get_task("t-conn")
    _ = ledger.list_recent_tasks(limit=10)

    # On Windows, if connection is properly closed, we can rename or delete the db file without PermissionError
    import os
    rename_target = tmp_path / "test_conn_close_renamed.db"
    os.rename(db_file, rename_target)
    assert rename_target.exists()


def test_project_lock_upgrade_notifies_immediately():
    mgr = ProjectLockManager()
    project_path = "C:/TestProject/UpgradeNotify"

    # Main thread acquires read
    assert mgr.acquire_read(project_path) is True

    worker_read_done = threading.Event()

    def worker():
        mgr.acquire_read(project_path)
        worker_read_done.set()
        time.sleep(0.04)
        mgr.release_read(project_path)

    t = threading.Thread(target=worker)
    t.start()
    worker_read_done.wait()

    # Upgrading: main thread acquires write with 1s timeout
    t0 = time.time()
    acquired = mgr.acquire_write(project_path, timeout=1.0)
    elapsed = time.time() - t0

    t.join()
    assert acquired is True
    # Worker finishes in 0.04s, so upgrade must complete well before 0.5s (not blocked until timeout)
    assert elapsed < 0.45, f"Upgrade took too long ({elapsed:.3f}s), condition notification was not received!"

    mgr.release_write(project_path)
    mgr.release_read(project_path)


def test_project_lock_writer_timeout_wakes_waiting_readers():
    mgr = ProjectLockManager()
    project_path = "C:/TestProject/WriterTimeoutNotify"

    # Thread 1 holds read lock
    assert mgr.acquire_read(project_path) is True

    writer_started = threading.Event()
    reader2_done = threading.Event()
    reader2_waited = [0.0]

    def writer():
        writer_started.set()
        # Writer attempts write with 0.05s timeout and fails
        mgr.acquire_write(project_path, timeout=0.05)

    def reader2():
        writer_started.wait()
        time.sleep(0.01)
        t0 = time.time()
        acq = mgr.acquire_read(project_path, timeout=1.0)
        reader2_waited[0] = time.time() - t0
        assert acq is True
        mgr.release_read(project_path)
        reader2_done.set()

    tw = threading.Thread(target=writer)
    tr = threading.Thread(target=reader2)

    tw.start()
    tr.start()

    tw.join()  # Writer times out
    time.sleep(0.02)
    # Thread 1 releases its read lock
    mgr.release_read(project_path)

    reader2_done.wait(timeout=1.0)
    tr.join()
    assert reader2_done.is_set()


def test_bridge_code_modifying_intent_turkish_conjugations():
    bridge = AgyProcessBridge()

    # Natural Turkish verb conjugations and specific user prompts
    modifying = [
        "O zaman gerekli olan güncellemeleri yapalım.",
        "Yeni testleri ekleyelim",
        "Hatayı düzeltelim",
        "Dosyayı değiştirelim",
        "Yeni bir fonksiyon yazalım",
        "Kod tabanında refactor yapalım",
        "Gereksiz dosyaları silelim",
        "Modülü güncelleyelim mi?",
        "Can you fix this bug?",
        "Update the code please",
        "Implement the task ledger",
    ]
    for prompt in modifying:
        assert bridge.is_code_modifying_intent(prompt) is True, f"Failed to classify modifying prompt: {prompt}"

    # Pure conversational / informational questions
    conversational = [
        "Merhaba, nasılsın?",
        "Python kodları nasıl çalışır?",
        "Bu projenin mimarisi nedir?",
        "Obsidian hafızasındaki notları listele",
        "Explain how reader writer lock works",
        "What is the current time?",
    ]
    for prompt in conversational:
        assert bridge.is_code_modifying_intent(prompt) is False, f"Falsely classified conversational prompt as modifying: {prompt}"


def test_bridge_background_task_unexpected_exception_ledger_status(tmp_path, monkeypatch):
    bridge = AgyProcessBridge()
    bridge.set_project_directory(tmp_path)

    test_ledger = TaskLedger(db_path=tmp_path / "outer_err_ledger.db")
    monkeypatch.setattr("entropy.core.agy_bridge.task_ledger", test_ledger)

    from entropy.core.project_lock import project_lock_manager

    task_id = "test-outer-err-01"

    # Simulate an unhandled crash inside find_agy_executable
    def crashing_find():
        raise RuntimeError("Disk I/O Error during executable lookup")

    monkeypatch.setattr(bridge, "find_agy_executable", crashing_find)

    bridge._execute_background_task_worker(
        task_id=task_id,
        task_name="Crashing Job",
        prompt="Crash test",
        mode="accept-edits"
    )

    # Task should be marked as FAILED in ledger, not left as RUNNING
    task = test_ledger.get_task(task_id)
    assert task is not None
    assert task["status"] == TaskStatus.FAILED.value
    assert "Disk I/O Error" in task["error"]

    # Lock must be fully released
    assert project_lock_manager.is_write_locked(tmp_path) is False



# =====================================================================
# Faz 12 kapanışı — sohbet turu defterde ölçülür
# =====================================================================

def test_chat_turn_usage_is_recorded_and_separable(tmp_path):
    """
    Sohbet turu tüketimi deftere yazılır; görev maliyetinden AYRI okunabilir.

    Tavan aşımının nedeni ölçülemeyen sohbet tüketimiydi: defter yalnızca arka
    plan görevlerini tutuyordu.
    """
    ledger = TaskLedger(db_path=tmp_path / "chat.db")

    ledger.record_task_start("task-1", "Görev", str(tmp_path))
    ledger.record_task_success("task-1", "bitti",
                               usage={"input_tokens": 100, "output_tokens": 50,
                                      "total_tokens": 150})

    row_id = ledger.record_chat_turn(
        {"input_tokens": 8000, "output_tokens": 400, "total_tokens": 8400},
        provider="agy", model="gemini-3.8-flash-low")
    assert row_id and row_id.startswith("chat-")

    rec = ledger.get_task(row_id)
    assert rec["status"] == TaskStatus.SUCCESS.value
    assert rec["provider"] == "agy"
    assert rec["model"] == "gemini-3.8-flash-low"
    assert rec["total_tokens"] == 8400

    # Sıfır tokenli tur defteri şişirmez.
    assert ledger.record_chat_turn({"total_tokens": 0}, provider="claude") is None

    chat = ledger.chat_token_totals()
    assert chat["turns"] == 1 and chat["total_tokens"] == 8400
    # Genel toplam ikisini de kapsar (görev 150 + sohbet 8400).
    assert ledger.token_totals()["total_tokens"] == 8550
