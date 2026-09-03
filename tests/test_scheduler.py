"""Automated tests for Task Scheduler and Windows Platform components."""

import time
import pytest
from pathlib import Path

from entropy.scheduler.cron_engine import TaskScheduler, ScheduledTask
from entropy.platform.autostart import WindowsAutostartManager
from entropy.platform.clipboard import ClipboardImageHandler

def test_scheduler_intervals(tmp_path):
    storage = tmp_path / "test_tasks.json"
    scheduler = TaskScheduler(storage_path=storage)

    now = 1700000000.0  # reference epoch

    # Minutely (e.g. every 15 mins)
    next_min = scheduler.compute_next_run("minutely", 15, from_time=now)
    assert next_min == now + (15 * 60.0)

    # Hourly (e.g. every 2 hours)
    next_hr = scheduler.compute_next_run("hourly", 2, from_time=now)
    assert next_hr == now + (2 * 3600.0)

    # Daily & Weekly compute valid future epoch
    next_daily = scheduler.compute_next_run("daily", 9, from_time=now)
    assert next_daily > now

    next_weekly = scheduler.compute_next_run("weekly", 10, day_of_week=0, from_time=now)
    assert next_weekly > now

def test_scheduler_persistence_and_trigger(tmp_path):
    storage = tmp_path / "test_tasks.json"
    scheduler = TaskScheduler(storage_path=storage)

    task = scheduler.schedule_task(
        task_id="task-1",
        name="Daily Git Review",
        prompt="Audit git diff and summarize",
        interval_type="minutely",
        interval_value=1
    )
    assert task.id in scheduler.tasks
    assert storage.exists()

    # Verify reloading from disk
    reloaded = TaskScheduler(storage_path=storage)
    assert "task-1" in reloaded.tasks
    assert reloaded.tasks["task-1"].name == "Daily Git Review"

def test_windows_autostart_manager(tmp_path):
    mgr = WindowsAutostartManager(app_name="TestEntropy")
    mgr.startup_dir = tmp_path
    mgr.startup_bat = tmp_path / "TestEntropy.bat"

    assert not mgr.is_autostart_enabled()

    ok = mgr.enable_autostart(python_exe="python.exe", script_path="main.py")
    assert ok is True
    assert mgr.is_autostart_enabled()
    assert "TestEntropy.bat" in [f.name for f in tmp_path.iterdir()]

    disable_ok = mgr.disable_autostart()
    assert disable_ok is True
    assert not mgr.is_autostart_enabled()

def test_clipboard_handler_init(tmp_path):
    staging = tmp_path / "staging"
    handler = ClipboardImageHandler(staging_dir=staging)
    assert staging.exists()
