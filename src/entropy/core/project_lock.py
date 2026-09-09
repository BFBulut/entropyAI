"""Single-Writer Smart Project Lock with Reader-Writer concurrency control.

Guarantees thread-safe shared read access for conversational requests and exclusive
write access for autonomous background mutating tasks and code modifications.
"""

import collections
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional


# Kilit zaman aşımıyla hiç başlayamayan arka plan görevinin hata metnine konan
# işaret. Çağıran (ofis harness'ı) bunu görünce kartı "başarısız" saymak yerine
# sıraya geri koyar: iş yanlış yapılmadı, hiç başlamadı.
LOCK_TIMEOUT_MARKER = "[proje-kilidi-zaman-asimi]"


class _ProjectRWLock:
    """Reader-Writer Lock for a single normalized project directory.

    Allows concurrent readers when no writer is active.
    Ensures exclusive write access for mutating operations.
    Thread-safe and supports re-entrancy for the same thread.
    """

    def __init__(self, path: str):
        self.path: str = path
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)

        # Write state
        self._active_writer_id: Optional[int] = None
        self._writer_recursion: int = 0
        self._waiting_writers: int = 0

        # Read state: thread_id -> count of re-entrant read locks
        self._reader_counts: collections.defaultdict[int, int] = collections.defaultdict(int)
        self._total_readers: int = 0

    def acquire_write(self, timeout: Optional[float] = None) -> bool:
        """Acquire exclusive write access for current thread."""
        tid = threading.get_ident()
        with self._lock:
            # 1. Re-entrant write acquisition on the same thread
            if self._active_writer_id == tid:
                self._writer_recursion += 1
                return True

            end_time = (time.time() + timeout) if timeout is not None else None
            self._waiting_writers += 1
            try:
                while True:
                    # Can write if no other writer is active and only current thread has read locks (if any)
                    current_thread_reads = self._reader_counts.get(tid, 0)
                    other_readers = self._total_readers - current_thread_reads

                    if self._active_writer_id is None and other_readers == 0:
                        self._active_writer_id = tid
                        self._writer_recursion = 1
                        return True

                    if timeout is not None:
                        remaining = end_time - time.time()
                        if remaining <= 0:
                            return False
                        self._cond.wait(remaining)
                    else:
                        self._cond.wait()
            finally:
                self._waiting_writers -= 1
                self._cond.notify_all()

    def release_write(self) -> None:
        """Release exclusive write access previously acquired by current thread."""
        tid = threading.get_ident()
        with self._lock:
            if self._active_writer_id != tid:
                raise RuntimeError(
                    f"Thread {tid} cannot release write lock on '{self.path}' because it does not hold it "
                    f"(active writer is {self._active_writer_id})."
                )
            self._writer_recursion -= 1
            if self._writer_recursion == 0:
                self._active_writer_id = None
                self._cond.notify_all()

    def acquire_read(self, timeout: Optional[float] = None) -> bool:
        """Acquire shared read access for current thread."""
        tid = threading.get_ident()
        with self._lock:
            # 1. Active writer can also read (read-during-write)
            if self._active_writer_id == tid:
                self._reader_counts[tid] += 1
                self._total_readers += 1
                return True

            # 2. Re-entrant read for a thread that already holds read lock
            if self._reader_counts.get(tid, 0) > 0:
                self._reader_counts[tid] += 1
                self._total_readers += 1
                return True

            end_time = (time.time() + timeout) if timeout is not None else None
            # Wait if another thread holds write lock or if writers are waiting
            while self._active_writer_id is not None or self._waiting_writers > 0:
                if timeout is not None:
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
                else:
                    self._cond.wait()

            self._reader_counts[tid] += 1
            self._total_readers += 1
            return True

    def release_read(self) -> None:
        """Release shared read access previously acquired by current thread."""
        tid = threading.get_ident()
        with self._lock:
            if self._reader_counts.get(tid, 0) <= 0:
                raise RuntimeError(
                    f"Thread {tid} cannot release read lock on '{self.path}' because it holds no read lock."
                )
            self._reader_counts[tid] -= 1
            if self._reader_counts[tid] == 0:
                del self._reader_counts[tid]
            self._total_readers -= 1

            # Notify all waiters (both waiting writers and upgrading writers)
            self._cond.notify_all()

    @property
    def is_write_locked(self) -> bool:
        with self._lock:
            return self._active_writer_id is not None

    @property
    def is_locked(self) -> bool:
        with self._lock:
            return self._active_writer_id is not None or self._total_readers > 0

    @property
    def total_readers(self) -> int:
        with self._lock:
            return self._total_readers

    @property
    def waiting_writers(self) -> int:
        with self._lock:
            return self._waiting_writers


class ProjectLockManager:
    """Manages Single-Writer Smart Locks across normalized project paths."""

    def __init__(self):
        self._global_lock = threading.RLock()
        self._locks: Dict[str, _ProjectRWLock] = {}

    def _normalize(self, project_path: Path | str) -> str:
        try:
            resolved = Path(project_path).resolve()
            norm = str(resolved)
        except Exception:
            norm = os.path.abspath(str(project_path))
        if os.name == "nt":
            norm = os.path.normcase(norm)
        return norm

    def _get_lock(self, project_path: Path | str) -> _ProjectRWLock:
        norm = self._normalize(project_path)
        with self._global_lock:
            if norm not in self._locks:
                self._locks[norm] = _ProjectRWLock(norm)
            return self._locks[norm]

    def acquire_write(self, project_path: Path | str, timeout: Optional[float] = None) -> bool:
        """Acquire exclusive write lock on project path."""
        return self._get_lock(project_path).acquire_write(timeout=timeout)

    def release_write(self, project_path: Path | str) -> None:
        """Release exclusive write lock on project path."""
        self._get_lock(project_path).release_write()

    def acquire_read(self, project_path: Path | str, timeout: Optional[float] = None) -> bool:
        """Acquire shared read lock on project path."""
        return self._get_lock(project_path).acquire_read(timeout=timeout)

    def release_read(self, project_path: Path | str) -> None:
        """Release shared read lock on project path."""
        self._get_lock(project_path).release_read()

    def is_write_locked(self, project_path: Path | str) -> bool:
        """Check if project path is currently write-locked."""
        return self._get_lock(project_path).is_write_locked

    def is_locked(self, project_path: Path | str) -> bool:
        """Check if project path has any active read or write lock."""
        return self._get_lock(project_path).is_locked

    def get_lock_state(self, project_path: Path | str) -> Dict[str, Any]:
        """Return snapshot of lock state for diagnosis and monitoring."""
        rw = self._get_lock(project_path)
        with rw._lock:
            return {
                "project_path": rw.path,
                "is_write_locked": rw.is_write_locked,
                "active_writer_id": rw._active_writer_id,
                "total_readers": rw.total_readers,
                "waiting_writers": rw.waiting_writers,
            }

    @contextmanager
    def write_lock(self, project_path: Path | str, timeout: Optional[float] = None):
        """Context manager for exclusive write access with guaranteed cleanup."""
        acquired = self.acquire_write(project_path, timeout=timeout)
        if not acquired:
            raise TimeoutError(f"Could not acquire write lock for project: {project_path}")
        try:
            yield
        finally:
            self.release_write(project_path)

    @contextmanager
    def read_lock(self, project_path: Path | str, timeout: Optional[float] = None):
        """Context manager for shared read access with guaranteed cleanup."""
        acquired = self.acquire_read(project_path, timeout=timeout)
        if not acquired:
            raise TimeoutError(f"Could not acquire read lock for project: {project_path}")
        try:
            yield
        finally:
            self.release_read(project_path)

    def reset(self) -> None:
        """Reset all tracked locks (useful for testing)."""
        with self._global_lock:
            self._locks.clear()


project_lock_manager = ProjectLockManager()
