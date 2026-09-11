"""Autonomous Periodic Task Scheduler for Entropy AI (Minutely, Hourly, Daily, Weekly)."""

import datetime
import json
import os
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from entropy.core.event_bus import bus

#: Zamanlayıcı kayıt dosyasını yönlendiren ortam değişkeni (testler için).
SCHEDULER_TASKS_ENV = "ENTROPY_SCHEDULER_TASKS"


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
    task_type: str = "analiz" # "analiz" or "kodlama"
    project_path: Optional[str] = None

class TaskScheduler:
    """Cron-like background task manager executing off the UI thread."""
    _instance: Optional["TaskScheduler"] = None

    @classmethod
    def get_instance(cls, storage_path: Optional[Path] = None) -> "TaskScheduler":
        """Retrieve or initialize the global singleton scheduler."""
        if cls._instance is None:
            cls._instance = cls(storage_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """Cleanly stop and reset the singleton instance."""
        if cls._instance is not None:
            cls._instance.stop()
            cls._instance = None

    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            # Faz 14-F: yalıtım kaçağı ölçüldü — tam süit sırasında zamanlayıcı
            # KULLANICININ gerçek `~/.entropy/scheduler_tasks.json` dosyasına
            # yazıyor ve saatlik işleri (obsidian-sync, rag-reindex) gerçekten
            # koşuyordu. Ledger ve bilişsel DB gibi burası da bir ortam
            # değişkeniyle yönlendirilebilir; değişken yoksa davranış aynıdır.
            override = os.environ.get(SCHEDULER_TASKS_ENV)
            if override:
                self.storage_path = Path(override).expanduser()
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            else:
                entropy_home = Path.home() / ".entropy"
                entropy_home.mkdir(parents=True, exist_ok=True)
                self.storage_path = entropy_home / "scheduler_tasks.json"
        else:
            self.storage_path = Path(storage_path)

        self.tasks: Dict[str, ScheduledTask] = {}
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
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
                    t_dict = dict(t)
                    t_dict.setdefault("task_type", "analiz")
                    t_dict.setdefault("project_path", None)
                    self.tasks[t["id"]] = ScheduledTask(**t_dict)
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
        day_of_week: Optional[int] = None,
        task_type: str = "analiz",
        project_path: Optional[str] = None
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
            next_run=next_run,
            task_type=task_type,
            project_path=project_path
        )
        self.tasks[task_id] = task
        self._save_tasks()
        return task

    def disable_task(self, task_id: str, reason: str = "") -> bool:
        """
        Zamanlanmış görevi kapatır (silmez) ve kullanıcıya nedenini duyurur.

        Faz 11.6 (öz-amplifikasyon kilidi): "her on dakikada aynı konuyu
        araştır" türü bir görev yinelenen çıktı üretmeye başladığında sonsuza
        dek koşmamalı. SİLİNMEZ çünkü kullanıcı hem nedenini görebilmeli hem
        de isterse yeniden açabilmeli.
        """
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None or not task.enabled:
                return False
            task.enabled = False
            self._save_tasks()
        try:
            bus.terminal_output_received.emit(
                f"[Otonom Görev] '{task.name}' durduruldu"
                + (f": {reason}" if reason else "") + "\n"
            )
        except Exception:
            pass
        return True

    def remove_task(self, task_id: str) -> bool:
        """Remove a task by ID and persist changes."""
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                self._save_tasks()
                return True
            return False

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
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self._thread.start()

    def stop(self, timeout: float = 1.0):
        """Stop the background scheduler loop."""
        with self._lock:
            self._running = False
            self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            self._thread = None

    def __del__(self):
        try:
            self.stop(timeout=0.2)
        except Exception:
            pass

    def _scheduler_loop(self):
        while self._running and not self._stop_event.is_set():
            now = time.time()
            triggered = []

            with self._lock:
                for task in self.tasks.values():
                    if task.enabled and task.next_run and now >= task.next_run:
                        triggered.append(task)

            for task in triggered:
                if not self._running or self._stop_event.is_set():
                    break
                bus.task_triggered.emit(task.id, task.name)
                if self._callback:
                    try:
                        self._callback(task)
                    except Exception:
                        bus.task_completed.emit(task.id, False)

                # Update schedule
                task.last_run = now
                task.next_run = self.compute_next_run(
                    task.interval_type, task.interval_value, task.day_of_week, from_time=now
                )
                self._save_tasks()

            self._stop_event.wait(1.0)
