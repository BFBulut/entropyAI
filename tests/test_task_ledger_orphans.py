"""Önceki oturumdan yetim kalan RUNNING görevler açılışta FAILED'a çekilir."""

from entropy.core.task_ledger import TaskLedger, TaskStatus


def test_mark_orphans_failed_only_touches_running_and_pending(tmp_path):
    led = TaskLedger(db_path=tmp_path / "l.db")
    led.record_task_start("a", "Damıtma [0→24/123]", str(tmp_path))
    led.record_task_pending("b", "Bekleyen", str(tmp_path))
    led.record_task_start("c", "Bitti", str(tmp_path))
    led.record_task_success("c", summary="ok")

    assert led.mark_orphans_failed() == 2
    assert led.get_task("a")["status"] == TaskStatus.FAILED.value
    assert "kapandı" in led.get_task("a")["error"]
    assert led.get_task("b")["status"] == TaskStatus.FAILED.value
    assert led.get_task("c")["status"] == TaskStatus.SUCCESS.value
    assert led.get_active_tasks() == []
    assert led.mark_orphans_failed() == 0, "ikinci çağrı boş dönmeli"
