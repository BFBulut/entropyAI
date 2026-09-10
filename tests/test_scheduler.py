"""Automated tests for Task Scheduler and Windows Platform components."""

import time
import pytest
from pathlib import Path

from entropy.scheduler.cron_engine import TaskScheduler, ScheduledTask
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

def test_clipboard_handler_init(tmp_path):
    staging = tmp_path / "staging"
    handler = ClipboardImageHandler(staging_dir=staging)
    assert staging.exists()

def test_task_execution_flow(tmp_path):
    storage = tmp_path / "test_tasks.json"
    scheduler = TaskScheduler(storage_path=storage)
    executed = []

    scheduler.set_execution_callback(lambda t: executed.append(t.id))
    task = scheduler.schedule_task(
        task_id="sample-task",
        name="Sample Autonomous Task",
        prompt="Perform sample check",
        interval_type="minutely",
        interval_value=1
    )
    # Trigger execution directly
    if scheduler._callback:
        scheduler._callback(task)

    assert len(executed) == 1
    assert executed[0] == "sample-task"

def test_scheduler_remove_task(tmp_path):
    storage = tmp_path / "test_tasks_remove.json"
    scheduler = TaskScheduler(storage_path=storage)
    scheduler.schedule_task("task-to-remove", "Temporary Task", "Do something", "hourly", 1)
    assert "task-to-remove" in scheduler.tasks

    # Remove task
    ok = scheduler.remove_task("task-to-remove")
    assert ok is True
    assert "task-to-remove" not in scheduler.tasks

    # Verify persisted removal
    reloaded = TaskScheduler(storage_path=storage)
    assert "task-to-remove" not in reloaded.tasks

    # Removing non-existent task returns False
    assert scheduler.remove_task("non-existent") is False
