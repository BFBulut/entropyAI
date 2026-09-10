"""SQLite Task FSM Ledger for autonomous background tasks and job lifecycle tracking."""

import datetime
import os
import sqlite3
import threading
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


#: Sohbet turu satırlarının adı (defterde göreve benzemesin diye açık).
CHAT_TURN_NAME = "Sohbet turu"


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
            # `ENTROPY_TASK_LEDGER_DB` varsayilani gecersiz kilar: test
            # kosumlari aksi hâlde kullanicinin GERCEK gorev defterine
            # (pytest tmp yollariyla) satir ekliyordu.
            _override = os.environ.get("ENTROPY_TASK_LEDGER_DB", "").strip()
            self.db_path = (
                Path(_override) if _override
                else Path.home() / ".entropy" / "tasks_ledger.db"
            )
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
                # Sağlayıcı sütunu: aynı defterde artık hem agy hem claude
                # görevleri var; hangisinin ne harcadığı ayrılamazsa token
                # toplamları anlamsızlaşır. Göç geriye uyumlu: eski satırlar
                # NULL kalır ve okurken "agy" varsayılır (o dönemde tek
                # sağlayıcı oydu), sütun eklenirken varsayılan atanmaz ki
                # gerçekten bilinmeyen değerle varsayım karışmasın.
                if "provider" not in cols:
                    conn.execute("ALTER TABLE tasks ADD COLUMN provider TEXT")
                # Model sütunu (Faz 9.5): kartın `model` alanı yürütmeye hiç
                # geçmiyordu ve hangi modelin koştuğu defterden okunamadığı için
                # hata günlerce görünmez kaldı. Göç geriye uyumlu: eski satırlar
                # NULL kalır, okurken "" varsayılır.
                if "model" not in cols:
                    conn.execute("ALTER TABLE tasks ADD COLUMN model TEXT")
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

    def record_task_start(
        self,
        task_id: str,
        task_name: str,
        project_path: str,
        provider: str = "agy",
        model: str = "",
    ) -> None:
        """
        Transition task status to RUNNING and record started_at timestamp.

        provider: görevi yürüten CLI ("agy" | "claude"). Varsayılanı "agy":
        eski çağrı yerleri (zamanlayıcı, testler) parametresiz çağırmaya devam
        edebilsin diye geriye uyumlu.
        """
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
                            completed_at = NULL, error = NULL, result_summary = NULL,
                            provider = ?, model = ?
                        WHERE task_id = ?
                        """,
                        (task_name, str(project_path), TaskStatus.RUNNING.value, now,
                         provider, model or "", task_id)
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO tasks (
                            task_id, task_name, project_path, status,
                            created_at, started_at, completed_at, error, result_summary,
                            provider, model
                        )
                        VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
                        """,
                        (task_id, task_name, str(project_path), TaskStatus.RUNNING.value,
                         now, now, provider, model or "")
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

    def record_chat_turn(
        self,
        usage: Optional[Dict[str, int]] = None,
        provider: str = "",
        model: str = "",
        task_id: str = "",
    ) -> Optional[str]:
        """
        Bir SOHBET turunun token maliyetini deftere yazar (Faz 12 kapanışı).

        Neden: defter yalnızca arka plan GÖREVLERİNİ tutuyordu; kullanıcının
        sohbet turları hiçbir yerde birikmiyordu. Tavan aşımının nedeni tam
        buydu — ölçülemeyen tüketim. Satırın kimliği `chat-<zaman>` ve durumu
        doğrudan SUCCESS: sohbet turu bittiğinde ölçülür, "süren" hâli yoktur.

        Sıfır tokenli tur YAZILMAZ (defteri boş satırla şişirmez); dönüş
        yazılan satırın kimliği ya da None.
        """
        u = usage or {}
        tok_in = int(u.get("input_tokens") or 0)
        tok_out = int(u.get("output_tokens") or 0)
        tok_total = int(u.get("total_tokens") or 0) or (tok_in + tok_out)
        if tok_total <= 0:
            return None
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        row_id = task_id or f"chat-{now_dt.strftime('%Y%m%d-%H%M%S-%f')}"
        now = now_dt.isoformat()
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        task_id, task_name, project_path, status,
                        created_at, started_at, completed_at, error, result_summary,
                        input_tokens, output_tokens, total_tokens, provider, model
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        input_tokens = excluded.input_tokens,
                        output_tokens = excluded.output_tokens,
                        total_tokens = excluded.total_tokens
                    """,
                    (row_id, CHAT_TURN_NAME, "", TaskStatus.SUCCESS.value,
                     now, now, now, CHAT_TURN_NAME,
                     tok_in, tok_out, tok_total, provider or "", model or "")
                )
                conn.commit()
        return row_id

    def chat_token_totals(self, since_iso: Optional[str] = None) -> Dict[str, int]:
        """Yalnızca sohbet turlarının toplamı (`chat-` ön ekli satırlar)."""
        with self._lock:
            with self._get_connection() as conn:
                sql = ("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), "
                       "COALESCE(SUM(total_tokens),0), COUNT(*) FROM tasks "
                       "WHERE task_id LIKE 'chat-%'")
                if since_iso:
                    row = conn.execute(sql + " AND completed_at >= ?", (since_iso,)).fetchone()
                else:
                    row = conn.execute(sql).fetchone()
        return {"input_tokens": row[0], "output_tokens": row[1],
                "total_tokens": row[2], "turns": row[3]}

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

    def _record_terminal(
        self,
        task_id: str,
        status: str,
        detail: str,
        task_name: str,
        project_path: str,
        usage: Optional[Dict[str, int]],
    ) -> None:
        """
        FAILED/CANCELLED satırını yazar; usage biliniyorsa token sütunlarını da.

        Faz 7 (A7a): eskiden yalnızca `record_task_success` usage yazıyordu.
        Süreç yarıda ölünce satırın `total_tokens` sütunu NULL kalıyor, ofis
        harness'ı gerçek maliyeti okuyamıyor ve karakter/4 tahminine düşüyordu —
        yani en pahalı senaryoda (yanıt vermeden ölen agy) bütçe koruması kör
        oluyordu. Akıştan okunan SON usage burada da yazılır.
        """
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
                        SET status = ?, completed_at = ?, error = ?,
                            input_tokens = COALESCE(?, input_tokens),
                            output_tokens = COALESCE(?, output_tokens),
                            total_tokens = COALESCE(?, total_tokens)
                        WHERE task_id = ?
                        """,
                        (status, now, detail, tok_in, tok_out, tok_total, task_id)
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO tasks (
                            task_id, task_name, project_path, status,
                            created_at, started_at, completed_at, error, result_summary,
                            input_tokens, output_tokens, total_tokens
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                        """,
                        (task_id, task_name or task_id, str(project_path), status,
                         now, now, now, detail, tok_in, tok_out, tok_total)
                    )
                conn.commit()

    def record_task_failure(
        self,
        task_id: str,
        error: str,
        task_name: str = "",
        project_path: str = "",
        usage: Optional[Dict[str, int]] = None,
    ) -> None:
        """Mark task as failed with error details (and last known token usage)."""
        self._record_terminal(
            task_id, TaskStatus.FAILED.value, str(error), task_name, project_path, usage
        )

    def record_task_cancelled(
        self,
        task_id: str,
        reason: str = "",
        task_name: str = "",
        project_path: str = "",
        usage: Optional[Dict[str, int]] = None,
    ) -> None:
        """Mark task as cancelled with optional reason (and last known token usage)."""
        self._record_terminal(
            task_id, TaskStatus.CANCELLED.value, str(reason), task_name, project_path, usage
        )

    @staticmethod
    def card_id_for(task_id: str) -> str:
        """
        Ledger görev kimliğinden kart kimliğini çıkarır.

        Köprü kimlikleri `card-<id>`, `office-plan-<id>`, `office-eval-<id>`
        biçiminde; terminal olay kartın kimliğiyle yayılmalı ki kanban ve
        `office_status` mesajı bulabilsin.
        """
        for prefix in ("card-", "office-plan-", "office-eval-"):
            if task_id.startswith(prefix):
                return task_id[len(prefix):]
        return task_id

    def _emit_terminal_events(self, task_ids: List[str], status: str, reason: str) -> None:
        """
        Toplu geçişlerden sonra her görev için terminal olay yayar.

        Faz 7 (A8): `mark_orphans_failed`/`cancel_active` yalnızca SQLite satırını
        çeviriyordu; posta kutusunda terminal olay olmadığı için kanban ve
        `office_status` kartı sonsuza dek "çalışıyor" gösteriyordu. Ajan katmanı
        çekirdeğe bağımlı olmasın diye içe aktarma GEÇ ve korumalı: posta kutusu
        yoksa ledger yine de doğru çalışır.
        """
        if not task_ids:
            return
        try:
            from entropy.agents.mailbox import emit_terminal
        except Exception:
            return
        for task_id in task_ids:
            try:
                emit_terminal(self.card_id_for(task_id), "desk", status, reason)
            except Exception:
                continue

    def _active_task_ids(self, conn) -> List[str]:
        return [
            row[0] for row in conn.execute(
                "SELECT task_id FROM tasks WHERE status IN (?, ?)",
                (TaskStatus.RUNNING.value, TaskStatus.PENDING.value),
            ).fetchall()
        ]

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
                orphans = self._active_task_ids(conn)
                cur = conn.execute(
                    """
                    UPDATE tasks SET status = ?, completed_at = ?, error = ?
                    WHERE status IN (?, ?)
                    """,
                    (TaskStatus.FAILED.value, now, reason, TaskStatus.RUNNING.value, TaskStatus.PENDING.value),
                )
                conn.commit()
                count = cur.rowcount or 0
        self._emit_terminal_events(orphans, "failed", reason)
        return count

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
                active = self._active_task_ids(conn)
                cur = conn.execute(
                    """
                    UPDATE tasks SET status = ?, completed_at = ?, error = ?
                    WHERE status IN (?, ?)
                    """,
                    (TaskStatus.CANCELLED.value, now, reason, TaskStatus.RUNNING.value, TaskStatus.PENDING.value),
                )
                conn.commit()
                count = cur.rowcount or 0
        self._emit_terminal_events(active, "canceled", reason)
        return count

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        """
        Satırı sözlüğe çevirir ve eksik sağlayıcıyı "agy" olarak doldurur.

        Sütun eklenmeden önce yazılmış satırlarda provider NULL'dur; o dönemde
        tek sağlayıcı agy olduğu için okuma tarafında varsayılır. Böylece görev
        paneli ve token raporu eski kayıtlarda boş sütun göstermez.
        """
        d = dict(row)
        if not d.get("provider"):
            d["provider"] = "agy"
        if "model" in d and d.get("model") is None:
            d["model"] = ""
        return d

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a task record by ID."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
                row = cur.fetchone()
                return self._row_to_dict(row) if row else None

    def list_recent_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent tasks ordered by creation time descending."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
                return [self._row_to_dict(r) for r in cur.fetchall()]

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Retrieve currently RUNNING or PENDING tasks."""
        with self._lock:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT * FROM tasks WHERE status IN (?, ?) ORDER BY created_at DESC",
                    (TaskStatus.RUNNING.value, TaskStatus.PENDING.value)
                )
                return [self._row_to_dict(r) for r in cur.fetchall()]

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
