"""SQLite Task FSM Ledger for autonomous background tasks and job lifecycle tracking."""

import datetime
import sqlite3
import threading
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    """Finite state machine statuses for autonomous tasks."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskLedger:
    """Thread-safe SQLite ledger tracking background task execution and states."""

    def __init__(self, db_path: Optional[Path | str] = None):
        if db_path is None:
            self.db_path = Path.home() / ".entropy" / "tasks_ledger.db"
        else:
            self.db_path = Path(db_path)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Yield an active SQLite connection and guarantee closure upon context exit."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        task_name TEXT NOT NULL,
                        project_path TEXT,
                        status TEXT NOT NULL,
                        created_at TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        error TEXT,
                        result_summary TEXT
                    )
                    """
                )
                # Token sütunları: görev başına gerçek AGY maliyeti. Eski veritabanları
                # sütunsuz olduğundan ALTER ile eklenir; eksikler NULL kalır.
                cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
                for col in ("input_tokens", "output_tokens", "total_tokens"):
                    if col not in cols:
                        conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} INTEGER")
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);"
                )
                conn.commit()

    def record_task_pending(self, task_id: str, task_name: str, project_path: str) -> None:
        """Record a newly queued task before execution begins."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        task_id, task_name, project_path, status,
                        created_at, started_at, completed_at, error, result_summary
                    )
                    VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                    ON CONFLICT(task_id) DO UPDATE SET
                        task_name = excluded.task_name,
                        project_path = excluded.project_path,
                        status = excluded.status,
                        started_at = NULL,
                        completed_at = NULL,
                        error = NULL,
                        result_summary = NULL
                    """,
                    (task_id, task_name, str(project_path), TaskStatus.PENDING.value, now)
                )
                conn.commit()

    def record_task_start(self, task_id: str, task_name: str, project_path: str) -> None:
        """Transition task status to RUNNING and record started_at timestamp."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT created_at FROM tasks WHERE task_id = ?", (task_id,))
                row = cur.fetchone()
                if row:
                    conn.execute(
                        """
                        UPDATE tasks
                        SET task_name = ?, project_path = ?, status = ?, started_at = ?,
                            completed_at = NULL, error = NULL, result_summary = NULL
                        WHERE task_id = ?
                        """,
                        (task_name, str(project_path), TaskStatus.RUNNING.value, now, task_id)
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO tasks (
                            task_id, task_name, project_path, status,
                            created_at, started_at, completed_at, error, result_summary
                        )
                        VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                        """,
                        (task_id, task_name, str(project_path), TaskStatus.RUNNING.value, now, now)
                    )
                conn.commit()

    def record_task_success(
        self,
        task_id: str,
        summary: str = "",
        task_name: str = "",
        project_path: str = "",
        usage: Optional[Dict[str, int]] = None,
    ) -> None:
        """Mark task as successfully completed with result summary (and token usage if known)."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        u = usage or {}
        tok_in = u.get("input_tokens")
        tok_out = u.get("output_tokens")
        tok_total = u.get("total_tokens")
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,))
                if cur.fetchone():
                    conn.execute(
                        """
                        UPDATE tasks
                        SET status = ?, completed_at = ?, result_summary = ?, error = NULL,
                            input_tokens = COALESCE(?, input_tokens),
                            output_tokens = COALESCE(?, output_tokens),
                            total_tokens = COALESCE(?, total_tokens)
                        WHERE task_id = ?
                        """,
                        (TaskStatus.SUCCESS.value, now, summary, tok_in, tok_out, tok_total, task_id)
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO tasks (
                            task_id, task_name, project_path, status,
                            created_at, started_at, completed_at, error, result_summary,
                            input_tokens, output_tokens, total_tokens
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
                        """,
                        (task_id, task_name or task_id, str(project_path), TaskStatus.SUCCESS.value,
                         now, now, now, summary, tok_in, tok_out, tok_total)
                    )
                conn.commit()

    def token_totals(self, since_iso: Optional[str] = None) -> Dict[str, int]:
        """Kayıtlı arka plan görevlerinin toplam token maliyeti (opsiyonel tarih filtresiyle)."""
        with self._lock:
            with self._get_connection() as conn:
                if since_iso:
                    row = conn.execute(
                        "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), "
                        "COALESCE(SUM(total_tokens),0), COUNT(total_tokens) FROM tasks WHERE completed_at >= ?",
                        (since_iso,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), "
                        "COALESCE(SUM(total_tokens),0), COUNT(total_tokens) FROM tasks"
                    ).fetchone()
        return {"input_tokens": row[0], "output_tokens": row[1], "total_tokens": row[2], "tasks_with_usage": row[3]}

    def record_task_failure(self, task_id: str, error: str, task_name: str = "", project_path: str = "") -> None:
        """Mark task as failed with error details."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,))
                if cur.fetchone():
                    conn.execute(
                        """
                        UPDATE tasks
                        SET status = ?, completed_at = ?, error = ?
                        WHERE task_id = ?
                        """,
                        (TaskStatus.FAILED.value, now, str(error), task_id)
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO tasks (
                            task_id, task_name, project_path, status,
                            created_at, started_at, completed_at, error, result_summary
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                        """,
                        (task_id, task_name or task_id, str(project_path), TaskStatus.FAILED.value, now, now, now, str(error))
                    )
                conn.commit()

    def record_task_cancelled(self, task_id: str, reason: str = "", task_name: str = "", project_path: str = "") -> None:
        """Mark task as cancelled with optional reason."""
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,))
                if cur.fetchone():
                    conn.execute(
                        """
                        UPDATE tasks
                        SET status = ?, completed_at = ?, error = ?
                        WHERE task_id = ?
                        """,
                        (TaskStatus.CANCELLED.value, now, str(reason), task_id)
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO tasks (
                            task_id, task_name, project_path, status,
                            created_at, started_at, completed_at, error, result_summary
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                        """,
                        (task_id, task_name or task_id, str(project_path), TaskStatus.CANCELLED.value, now, now, now, str(reason))
                    )
                conn.commit()

    def mark_orphans_failed(self, reason: str = "Önceki oturum bu görev sürerken kapandı; sonuç alınamadı.") -> int:
        """
        Önceki oturumdan RUNNING/PENDING kalmış satırları FAILED yapar; sayısını döndürür.

        Uygulama bir görev sürerken kapanırsa (çökme, kapatma) satır sonsuza dek
        "çalışıyor" görünür: görev panelinde hayalet bir iş, damıtma kilidi yok ama
        kullanıcı "arkada ne çalışıyor?" diye sorar. Süreç yeniden başlarken hiçbir
        işçi iş parçacığı yaşamadığı için bu satırların tamamı yetimdir.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    UPDATE tasks SET status = ?, completed_at = ?, error = ?
                    WHERE status IN (?, ?)
                    """,
                    (TaskStatus.FAILED.value, now, reason, TaskStatus.RUNNING.value, TaskStatus.PENDING.value),
                )
                conn.commit()
                return cur.rowcount or 0

    def cancel_active(self, reason: str = "Uygulama kapandı; görev yarıda kesildi.") -> int:
        """
        Çalışan/bekleyen tüm satırları CANCELLED yapar; sayısını döndürür.

        `mark_orphans_failed`'in kapanış ikizi. Fark kasıtlı: açılışta yetim
        bulmak bir arızadır (FAILED), kapanışta görevi biz kestiğimiz için bu
        bir arıza değil iptaldir (CANCELLED). İkisi ayrılmazsa kullanıcı her
        normal kapatmadan sonra panelde kırmızı "başarısız" satırlar görüyordu.
        """
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    UPDATE tasks SET status = ?, completed_at = ?, error = ?
                    WHERE status IN (?, ?)
                    """,
                    (TaskStatus.CANCELLED.value, now, reason, TaskStatus.RUNNING.value, TaskStatus.PENDING.value),
                )
                conn.commit()
                return cur.rowcount or 0

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a task record by ID."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def list_recent_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent tasks ordered by creation time descending."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
                return [dict(r) for r in cur.fetchall()]

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Retrieve currently RUNNING or PENDING tasks."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM tasks WHERE status IN (?, ?) ORDER BY created_at DESC",
                    (TaskStatus.RUNNING.value, TaskStatus.PENDING.value)
                )
                return [dict(r) for r in cur.fetchall()]

    def delete_task(self, task_id: str) -> bool:
        """Tek bir görev kaydını kayıt defterinden siler; silindiyse True döner."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
                conn.commit()
                return (cur.rowcount or 0) > 0

    def clear_finished(self) -> int:
        """Bitmiş (SUCCESS/FAILED/CANCELLED) kayıtları siler; silinen satır sayısını döner."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "DELETE FROM tasks WHERE status IN (?, ?, ?)",
                    (TaskStatus.SUCCESS.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value),
                )
                conn.commit()
                return cur.rowcount or 0

    def clear_all(self) -> None:
        """Clear all tasks from the ledger (primarily for testing)."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM tasks")
                conn.commit()


task_ledger = TaskLedger()
