"""Autonomous Periodic Task Scheduler for Entropy AI (Minutely, Hourly, Daily, Weekly)."""

import datetime
import json
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from entropy.core.event_bus import bus

@dataclass
class ScheduledTask:
    id: str
    name: str
    prompt: str
    interval_type: str  # "minutely", "hourly", "daily", "weekly"
    interval_value: int # e.g. every N mins, or hour 0-23
    day_of_week: Optional[int] = None # 0=Monday, 6=Sunday for weekly
    enabled: bool = True
    last_run: Optional[float] = None
    next_run: Optional[float] = None

class TaskScheduler:
    """Cron-like background task manager executing off the UI thread."""

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            entropy_home = Path.home() / ".entropy"
            entropy_home.mkdir(parents=True, exist_ok=True)
            self.storage_path = entropy_home / "scheduler_tasks.json"
        else:
            self.storage_path = Path(storage_path)

        self.tasks: Dict[str, ScheduledTask] = {}
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._callback: Optional[Callable[[ScheduledTask], None]] = None

        self._load_tasks()

    def set_execution_callback(self, callback: Callable[[ScheduledTask], None]):
        """Callback invoked when a task triggers (e.g. bridging to AGY)."""
        self._callback = callback

    def _load_tasks(self):
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for t in data:
                    self.tasks[t["id"]] = ScheduledTask(**t)
            except Exception:
                pass

    def _save_tasks(self):
        with self._lock:
            data = [asdict(t) for t in self.tasks.values()]
            self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def schedule_task(
        self,
        task_id: str,
        name: str,
        prompt: str,
        interval_type: str,
        interval_value: int,
        day_of_week: Optional[int] = None
    ) -> ScheduledTask:
        """Register a new recurring task."""
        now = time.time()
        next_run = self.compute_next_run(interval_type, interval_value, day_of_week, from_time=now)
        task = ScheduledTask(
            id=task_id,
            name=name,
            prompt=prompt,
            interval_type=interval_type,
            interval_value=interval_value,
            day_of_week=day_of_week,
            enabled=True,
            last_run=None,
            next_run=next_run
        )
        self.tasks[task_id] = task
        self._save_tasks()
        return task

    def compute_next_run(
        self,
        interval_type: str,
        interval_value: int,
        day_of_week: Optional[int] = None,
        from_time: Optional[float] = None
    ) -> float:
        """Calculate next epoch execution timestamp."""
        now = from_time or time.time()
        if interval_type == "minutely":
            return now + (interval_value * 60.0)
        elif interval_type == "hourly":
            return now + (interval_value * 3600.0)
        elif interval_type == "daily":
            # interval_value is the hour of day (0-23)
            dt = datetime.datetime.fromtimestamp(now)
            target = dt.replace(hour=interval_value, minute=0, second=0, microsecond=0)
            if target <= dt:
                target += datetime.timedelta(days=1)
            return target.timestamp()
        elif interval_type == "weekly":
            # interval_value is the hour of day, day_of_week is 0-6 (Mon-Sun)
            dow = day_of_week if day_of_week is not None else 0
            dt = datetime.datetime.fromtimestamp(now)
            days_ahead = (dow - dt.weekday()) % 7
            target = dt.replace(hour=interval_value, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_ahead)
            if target <= dt:
                target += datetime.timedelta(days=7)
            return target.timestamp()
        return now + 3600.0

    def start(self):
        """Start the background scheduler evaluation loop."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop the background scheduler loop."""
        with self._lock:
            self._running = False

    def _scheduler_loop(self):
        while self._running:
            now = time.time()
            triggered = []

            with self._lock:
                for task in self.tasks.values():
                    if task.enabled and task.next_run and now >= task.next_run:
                        triggered.append(task)

            for task in triggered:
                bus.task_triggered.emit(task.id, task.name)
                if self._callback:
                    try:
                        self._callback(task)
                        bus.task_completed.emit(task.id, True)
                    except Exception:
                        bus.task_completed.emit(task.id, False)

                # Update schedule
                task.last_run = now
                task.next_run = self.compute_next_run(
                    task.interval_type, task.interval_value, task.day_of_week, from_time=now
                )
                self._save_tasks()

            time.sleep(1.0)
