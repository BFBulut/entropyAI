"""Chat/Zen mod eşitliği, görev-yetenek yönetimi ve çekirdek görselleştirici testleri."""

import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from entropy.core.agy_bridge import AgyProcessBridge
from entropy.core.event_bus import bus
from entropy.core.task_ledger import TaskLedger, TaskStatus
from entropy.scheduler.cron_engine import TaskScheduler
from entropy.ui.modes.chat_mode import ChatModeWindow
from entropy.ui.modes.floating_mode import FloatingModeWidget
from entropy.ui.modes.zen_mode import ZenModeWindow
from entropy.ui.widgets.core_visualizer import (
    ACTIVE_FRAME_MS, IDLE_FRAME_MS, CoreVisualizerWidget
)
from entropy.ui.widgets.notification_pill import NotificationPillWidget
from entropy.ui.widgets.tasks_widget import TasksWidget


class _FakeBridgeProc:
    """Arka plan görevini sonlandırma çağrılarını kaydeden sahte köprü."""

    def __init__(self):
        self.terminated = []
        self.active_project_dir = None

    def terminate_background_task(self, task_id):
        self.terminated.append(task_id)


# --------------------------------------------------------------- Görev 1: eşitlik

def test_chat_mode_reacts_to_same_bus_signals_as_zen(qapp):
    bridge = AgyProcessBridge()
    chat = ChatModeWindow(bridge=bridge)

    assert hasattr(chat, "state_badge")
    assert hasattr(chat, "panel_btn")

    bus.core_state_changed.emit("thinking")
    assert "DÜŞÜNÜYOR" in chat.state_badge.text()

    bus.core_state_changed.emit("executing")
    assert "YÜRÜTÜLÜYOR" in chat.state_badge.text()

    bus.core_state_changed.emit("error")
    assert "HATA" in chat.state_badge.text()

    bus.task_triggered.emit("task-1", "Gece Analizi")
    assert "GÖREV" in chat.state_badge.text()

    bus.distill_progress.emit("financial-auditor", 2, 5)
    assert "DAMITMA 2/5" in chat.state_badge.text()

    bus.task_completed.emit("task-1", True)
    assert "HAZIR" in chat.state_badge.text()

    chat.close()


def test_chat_mode_report_creates_notification_pill(qapp, tmp_path):
    bridge = AgyProcessBridge()
    chat = ChatModeWindow(bridge=bridge)

    rep = tmp_path / "Parite_Raporu.md"
    rep.write_text("# Parite", encoding="utf-8")

    chat._on_report_created(str(rep))
    pills = [
        chat.notification_stack_layout.itemAt(i).widget()
        for i in range(chat.notification_stack_layout.count())
    ]
    assert any(isinstance(p, NotificationPillWidget) for p in pills)

    # Aynı rapor iki kez pil üretmemeli
    count_before = chat.notification_stack_layout.count()
    chat.add_notification_pill("Parite_Raporu", str(rep), is_task=False)
    assert chat.notification_stack_layout.count() == count_before

    chat.close()


def test_chat_side_panel_exposes_tasks_and_skills(qapp, tmp_path):
    TaskScheduler.reset_instance()
    TaskScheduler.get_instance(storage_path=tmp_path / "chat_panel_tasks.json")

    bridge = AgyProcessBridge()
    chat = ChatModeWindow(bridge=bridge)

    # Panel tembel yüklenir: açılmadan önce kurulmamış olmalı
    assert chat.side_panel is None
    assert chat.toggle_side_panel() is True
    assert chat.side_panel is not None
    assert chat._side_panel_open is True
    assert chat.tasks_widget is not None
    assert chat.skills_widget is not None
    tab_titles = [chat.side_panel.tabText(i) for i in range(chat.side_panel.count())]
    assert any("Görev" in t for t in tab_titles)
    assert any("Yetenek" in t for t in tab_titles)

    # Damıtma sayacı yetenek panelinde bulunuyor (Zen ile aynı widget)
    assert hasattr(chat.skills_widget, "_on_distill_progress")

    assert chat.toggle_side_panel() is False
    chat.close()


def test_work_started_in_one_mode_is_visible_in_other(qapp, tmp_path):
    """Bir modda başlatılan arka plan işi diğer modda da görünür (ortak bus)."""
    TaskScheduler.reset_instance()
    TaskScheduler.get_instance(storage_path=tmp_path / "cross_mode_tasks.json")

    bridge = AgyProcessBridge()
    zen = ZenModeWindow(bridge=bridge)
    chat = ChatModeWindow(bridge=bridge)
    chat.hide()  # kullanıcı Zen'de; Chat gizli ama canlı

    rep = tmp_path / "Cross_Mode.md"
    rep.write_text("# Cross", encoding="utf-8")
    bus.task_notification.emit("task-cross", "Çapraz Mod Görevi", str(rep))

    assert zen.notification_stack_layout.count() >= 1
    assert chat.notification_stack_layout.count() >= 1
    assert "Çapraz Mod Görevi" in chat.chat_browser.toPlainText()
    assert "Çapraz Mod Görevi" in zen.chat_browser.toPlainText()

    if getattr(zen, "tasks_widget", None) and zen.tasks_widget.scheduler:
        zen.tasks_widget.scheduler.stop()
    chat.close()
    zen.close()


# ------------------------------------------------- Görev 2: görev/yetenek yönetimi

def test_task_ledger_delete_and_clear_finished(tmp_path):
    ledger = TaskLedger(db_path=tmp_path / "ledger.db")
    ledger.record_task_start("t1", "Görev 1", str(tmp_path))
    ledger.record_task_success("t1", summary="bitti")
    ledger.record_task_start("t2", "Görev 2", str(tmp_path))

    assert ledger.delete_task("t1") is True
    assert ledger.get_task("t1") is None
    assert ledger.delete_task("yok") is False

    ledger.record_task_failure("t3", error="hata")
    removed = ledger.clear_finished()
    assert removed == 1                       # yalnızca bitmiş t3
    assert ledger.get_task("t2") is not None   # süren görev korunur


def test_tasks_widget_cancel_running_task(qapp, tmp_path, monkeypatch):
    import entropy.ui.widgets.tasks_widget as tw_mod

    ledger = TaskLedger(db_path=tmp_path / "cancel_ledger.db")
    monkeypatch.setattr(tw_mod, "task_ledger", ledger)

    scheduler = TaskScheduler(storage_path=tmp_path / "cancel_tasks.json")
    fake_bridge = _FakeBridgeProc()
    widget = TasksWidget(scheduler=scheduler, bridge=fake_bridge)

    task = scheduler.schedule_task(
        task_id="bg-1", name="Uzun Analiz", prompt="analiz et",
        interval_type="hourly", interval_value=2
    )
    ledger.record_task_start(task.id, task.name, str(tmp_path))
    widget.refresh_tasks()

    assert "bg-1" in widget.running_task_ids()
    stop_btn = widget.findChild(QPushButton, "task_stop_bg-1")
    assert stop_btn is not None and stop_btn.isEnabled()

    assert widget._on_cancel_task("bg-1", "Uzun Analiz", confirm=False) is True
    assert fake_bridge.terminated == ["bg-1"]
    assert ledger.get_task("bg-1")["status"] == TaskStatus.CANCELLED.value

    widget.close()
    scheduler.stop()


def test_tasks_widget_delete_clears_scheduler_and_ledger(qapp, tmp_path, monkeypatch):
    import entropy.ui.widgets.tasks_widget as tw_mod

    ledger = TaskLedger(db_path=tmp_path / "del_ledger.db")
    monkeypatch.setattr(tw_mod, "task_ledger", ledger)

    scheduler = TaskScheduler(storage_path=tmp_path / "del_tasks.json")
    widget = TasksWidget(scheduler=scheduler, bridge=_FakeBridgeProc())

    scheduler.schedule_task(
        task_id="bg-del", name="Silinecek", prompt="x",
        interval_type="minutely", interval_value=5
    )
    ledger.record_task_success("bg-del", summary="eski koşu")
    widget.refresh_tasks()

    assert widget._on_delete_task("bg-del", "Silinecek", confirm=False) is True
    assert "bg-del" not in scheduler.tasks
    assert ledger.get_task("bg-del") is None

    widget.close()
    scheduler.stop()


def test_tasks_widget_edit_updates_schedule(qapp, tmp_path, monkeypatch):
    import entropy.ui.widgets.tasks_widget as tw_mod

    monkeypatch.setattr(tw_mod, "task_ledger", TaskLedger(db_path=tmp_path / "edit_ledger.db"))
    scheduler = TaskScheduler(storage_path=tmp_path / "edit_tasks.json")
    widget = TasksWidget(scheduler=scheduler, bridge=_FakeBridgeProc())

    task = scheduler.schedule_task(
        task_id="bg-edit", name="Eski Ad", prompt="eski talimat",
        interval_type="hourly", interval_value=6
    )
    widget.refresh_tasks()
    edit_btn = widget.findChild(QPushButton, "task_edit_bg-edit")
    assert edit_btn is not None

    old_next = task.next_run
    time.sleep(0.01)
    widget.apply_task_edit(
        task, name="Yeni Ad", prompt="yeni talimat",
        interval_type="minutely", interval_value=15,
        task_type="kodlama", project_path=str(tmp_path)
    )

    assert scheduler.tasks["bg-edit"].name == "Yeni Ad"
    assert scheduler.tasks["bg-edit"].interval_type == "minutely"
    assert scheduler.tasks["bg-edit"].interval_value == 15
    assert scheduler.tasks["bg-edit"].task_type == "kodlama"
    assert scheduler.tasks["bg-edit"].next_run != old_next

    # Diske de yazılmış olmalı
    reloaded = TaskScheduler(storage_path=tmp_path / "edit_tasks.json")
    assert reloaded.tasks["bg-edit"].name == "Yeni Ad"

    widget.close()
    scheduler.stop()


def test_skills_widget_edit_and_folder_buttons(qapp, tmp_path):
    from entropy.skills.manager import SkillManager
    from entropy.ui.widgets.skills_widget import SkillEditorDialog, SkillsWidget

    skills_root = tmp_path / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)
    mgr = SkillManager(root_skills_dir=skills_root)
    mgr.create_skill("test-editor", "Düzenleme testi", "# Talimatlar\n\nAdım 1")

    widget = SkillsWidget(skill_manager=mgr)
    assert widget.findChild(QPushButton, "skill_edit_test-editor") is not None
    assert widget.findChild(QPushButton, "skill_folder_test-editor") is not None

    skill = [s for s in mgr.list_skills() if s.name == "test-editor"][0]
    dlg = SkillEditorDialog(skill.path, skill.name)
    assert "Talimatlar" in dlg.editor.toPlainText()

    dlg.editor.setPlainText(dlg.editor.toPlainText() + "\n\nAdım 2 (düzenlendi)")
    assert dlg.save() is True
    from pathlib import Path
    assert "düzenlendi" in Path(skill.path).read_text(encoding="utf-8")

    dlg.close()
    widget.close()


# ------------------------------------------------- Görev 3: çekirdek görselleştirici

def test_core_visualizer_smooth_state_transition(qapp):
    widget = CoreVisualizerWidget(base_radius=40)
    widget.set_state("error")

    assert widget.state == "error"
    assert widget._shake_frames > 0
    assert "Hata" in widget.toolTip()
    assert widget._shake_offset() != 0.0

    start_red = widget.glow_color.red()
    for _ in range(25):
        widget._animate_frame()
    assert widget.glow_color.red() > start_red      # kırmızıya doğru yumuşak geçiş
    assert widget.glow_color.red() > 200
    assert widget._shake_frames == 0                # titreme kısa sürer

    widget.close()


def test_core_visualizer_thinking_ripples_and_executing_particles(qapp):
    widget = CoreVisualizerWidget(base_radius=40)

    widget.set_state("thinking")
    for _ in range(5):
        widget._animate_frame()
    assert widget._ripples, "Düşünürken halka dalgası üretilmeli"
    assert not widget._particles

    widget.set_state("executing")
    assert widget._particles, "Yürütürken parçacık akışı olmalı"
    for _ in range(3):
        widget._animate_frame()
    assert all(0.0 <= p["angle"] <= 2 * 3.15 for p in widget._particles)

    widget.set_state("idle")
    assert not widget._particles

    widget.close()


def test_core_visualizer_frame_rate_is_capped_and_idles_down(qapp):
    widget = CoreVisualizerWidget(base_radius=40)

    # Etkin durumda en fazla 30 fps
    widget.set_state("thinking")
    assert widget.timer.interval() == ACTIVE_FRAME_MS
    assert ACTIVE_FRAME_MS >= 33  # <= 30 fps

    # Boşta kare hızı düşer
    widget.set_state("idle")
    widget.pulse_intensity = 0.0
    widget._ripples.clear()
    for _ in range(30):
        widget._animate_frame()
    assert widget.is_active() is False
    assert widget.timer.interval() == IDLE_FRAME_MS

    # Token geldiğinde tekrar hızlanır
    widget.trigger_pulse(0.9)
    assert widget.timer.interval() == ACTIVE_FRAME_MS

    widget.close()


def test_core_visualizer_mode_menu(qapp, monkeypatch):
    widget = CoreVisualizerWidget(base_radius=40, mode_menu_enabled=True)
    menu = widget.build_mode_menu()
    modes = [a.data() for a in menu.actions()]
    assert modes == ["zen", "chat", "floating"]

    received = []
    bus.mode_requested.connect(received.append)
    try:
        menu.actions()[0].trigger()
        assert received == ["zen"]
    finally:
        bus.mode_requested.disconnect(received.append)
    widget.close()


def _mouse_event(kind, widget):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent
    pos = QPointF(10.0, 10.0)
    return QMouseEvent(
        kind, pos, widget.mapToGlobal(pos.toPoint()).toPointF(),
        Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_floating_core_click_opens_mode_menu_without_breaking_drag(qapp):
    from PySide6.QtCore import QEvent

    widget = FloatingModeWidget()
    # Sürükleme korunsun diye görselleştirici tıklamayı yutmaz
    assert widget.visualizer.mode_menu_enabled is False

    opened = []
    widget.show_mode_menu = lambda pos: opened.append(pos)

    # Sürüklemesiz tek tık -> mod menüsü
    widget.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, widget))
    widget.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, widget))
    assert len(opened) == 1

    # Sürüklenmişse menü açılmaz (pencere taşınmıştır)
    widget.mousePressEvent(_mouse_event(QEvent.Type.MouseButtonPress, widget))
    widget.mouseMoveEvent(_mouse_event(QEvent.Type.MouseMove, widget))
    widget.mouseReleaseEvent(_mouse_event(QEvent.Type.MouseButtonRelease, widget))
    assert len(opened) == 1

    # Menü içeriği çekirdekle ortak
    assert [a.data() for a in widget.visualizer.build_mode_menu().actions()] == ["zen", "chat", "floating"]

    widget.close()


def test_zen_core_has_mode_menu_enabled(qapp, tmp_path):
    TaskScheduler.reset_instance()
    TaskScheduler.get_instance(storage_path=tmp_path / "zen_core_tasks.json")

    bridge = AgyProcessBridge()
    zen = ZenModeWindow(bridge=bridge)
    assert zen.core_visualizer.mode_menu_enabled is True

    if getattr(zen, "tasks_widget", None) and zen.tasks_widget.scheduler:
        zen.tasks_widget.scheduler.stop()
    zen.close()
