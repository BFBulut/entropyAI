"""Task Scheduler Management Widget for Zen Mode."""

import time
import datetime
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget, QCheckBox, QDialog,
    QLineEdit, QComboBox, QSpinBox, QMessageBox
)

from entropy.core.event_bus import bus
from entropy.scheduler.cron_engine import TaskScheduler, ScheduledTask
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
from entropy.ui.themes.cyber_theme import CYBER_THEME

class TasksWidget(QFrame):
    """Visual Task Scheduler displaying cron jobs, intervals, and manual triggers."""

    def __init__(self, parent=None, scheduler: Optional[TaskScheduler] = None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.scheduler = scheduler or TaskScheduler()

        # Seed default autonomous jobs if empty
        if not self.scheduler.tasks:
            self._seed_default_tasks()

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(6)

        # Header
        header = QHBoxLayout()
        title_label = QLabel("<b style='color:#00F0FF; font-size:13px;'>⏰ OTONOM ARKA PLAN GÖREVLERİ</b>")
        header.addWidget(title_label)
        header.addStretch()

        add_btn = QPushButton("+ Görev Ekle")
        add_btn.setFixedHeight(24)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00FF9D;
                border: 1px solid #00FF9D;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00FF9D;
                color: #080B10;
            }
        """)
        add_btn.clicked.connect(self._show_add_dialog)
        header.addWidget(add_btn)

        refresh_btn = QPushButton("Yenile")
        refresh_btn.setFixedHeight(24)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #141C2C;
                color: #00F0FF;
                border: 1px solid #00F0FF;
                border-radius: 4px;
                padding: 2px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00F0FF;
                color: #080B10;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_tasks)
        header.addWidget(refresh_btn)

        self.layout.addLayout(header)

        # Task list
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{
                background-color: {CYBER_THEME['bg_terminal']};
                border: 1px solid {CYBER_THEME['border']};
                border-radius: 4px;
                color: {CYBER_THEME['text_primary']};
                padding: 4px;
            }}
            QListWidget::item {{
                border-bottom: 1px solid #1F2B42;
                padding: 6px;
            }}
        """)
        self.layout.addWidget(self.list_widget)

        # Connect signals
        bus.task_triggered.connect(self._on_task_triggered)
        bus.task_completed.connect(self._on_task_completed)

        self.refresh_tasks()

    def _seed_default_tasks(self):
        """Seed default autonomous background cognitive tasks."""
        self.scheduler.schedule_task(
            task_id="daily-dreaming",
            name="Hafıza Konsolidasyonu & Rüya Görme (Mem0)",
            prompt="Periyodik bilişsel hafıza konsolidasyonu",
            interval_type="daily",
            interval_value=3  # 03:00 AM
        )
        self.scheduler.schedule_task(
            task_id="obsidian-sync",
            name="Obsidian Günlük Not & Hafıza Senkronu",
            prompt="Günlük not dosyalarını ve bellek haritasını güncelle",
            interval_type="hourly",
            interval_value=1
        )
        self.scheduler.schedule_task(
            task_id="rag-reindex",
            name="Proje Kod Tabanı İndeksleme (RAG)",
            prompt="Aktif proje dizinindeki yeni/değişen dosyaları tara",
            interval_type="hourly",
            interval_value=2
        )

    def refresh_tasks(self):
        """Populate the task list with custom row widgets."""
        self.list_widget.clear()

        for t_id, task in self.scheduler.tasks.items():
            item = QListWidgetItem()
            item.setSizeHint(QWidget().sizeHint())

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(6, 4, 6, 4)

            # Enable checkbox
            cb = QCheckBox()
            cb.setChecked(task.enabled)
            cb.toggled.connect(lambda checked, t=task: self._on_toggle_task(t, checked))
            row_layout.addWidget(cb)

            # Details
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)
            name_lbl = QLabel(f"<b style='color:#F0F6FC;'>{task.name}</b>")
            
            interval_str = f"Tip: {task.interval_type} ({task.interval_value})"
            next_str = datetime.datetime.fromtimestamp(task.next_run).strftime("%H:%M:%S") if task.next_run else "Planlanmadı"
            status_lbl = QLabel(f"<span style='color:#8B949E; font-size:11px;'>{interval_str} | Sonraki: {next_str}</span>")

            info_layout.addWidget(name_lbl)
            info_layout.addWidget(status_lbl)
            row_layout.addLayout(info_layout)
            row_layout.addStretch()

            # Run Now button
            run_btn = QPushButton("▶ Çalıştır")
            run_btn.setFixedHeight(22)
            run_btn.setStyleSheet("""
                QPushButton {
                    background-color: #141C2C;
                    color: #00F0FF;
                    border: 1px solid #00F0FF;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 10px;
                }
                QPushButton:hover {
                    background-color: #00F0FF;
                    color: #080B10;
                }
            """)
            run_btn.clicked.connect(lambda _, t=task: self._run_task_now(t))
            row_layout.addWidget(run_btn)

            item.setSizeHint(row_widget.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row_widget)

    def _on_toggle_task(self, task: ScheduledTask, enabled: bool):
        task.enabled = enabled
        self.scheduler._save_tasks()

    def _run_task_now(self, task: ScheduledTask):
        """Execute a task immediately and trigger its action."""
        bus.terminal_output_received.emit(f"\n[Task Scheduler] '{task.name}' görevi anlık olarak çalıştırılıyor...\n")
        
        # If it's the dreaming task, trigger cognitive consolidation
        if task.id == "daily-dreaming":
            try:
                cog = CognitiveMemorySystem()
                rules = cog.dream_and_consolidate()
                bus.terminal_output_received.emit(
                    f"[Task Scheduler] Bilişsel hafıza konsolidasyonu tamamlandı ({len(rules)} semantik kural sentezlendi).\n"
                )
            except Exception as e:
                bus.terminal_output_received.emit(f"[Task Scheduler Hata] Konsolidasyon hatası: {e}\n")

        bus.task_triggered.emit(task.id, task.name)
        task.last_run = time.time()
        task.next_run = self.scheduler.compute_next_run(
            task.interval_type, task.interval_value, task.day_of_week, from_time=time.time()
        )
        self.scheduler._save_tasks()
        self.refresh_tasks()

    @Slot(str, str)
    def _on_task_triggered(self, task_id: str, task_name: str):
        pass

    @Slot(str, bool)
    def _on_task_completed(self, task_id: str, success: bool):
        self.refresh_tasks()

    def _show_add_dialog(self):
        """Dialog to schedule a new recurring task."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Yeni Otonom Görev Ekle")
        dialog.setFixedWidth(380)
        dialog.setStyleSheet("background-color: #0E1420; color: #F0F6FC;")

        d_layout = QVBoxLayout(dialog)

        d_layout.addWidget(QLabel("Görev Adı:"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("örn: Proje Git Durumu Raporu")
        d_layout.addWidget(name_input)

        d_layout.addWidget(QLabel("Talimat / Prompt:"))
        prompt_input = QLineEdit()
        prompt_input.setPlaceholderText("örn: Git durumunu kontrol et ve özetle")
        d_layout.addWidget(prompt_input)

        d_layout.addWidget(QLabel("Tekrar Periyodu:"))
        type_combo = QComboBox()
        type_combo.addItems(["minutely", "hourly", "daily"])
        d_layout.addWidget(type_combo)

        d_layout.addWidget(QLabel("Periyot Değeri (Dakika / Saat):"))
        val_input = QSpinBox()
        val_input.setRange(1, 1440)
        val_input.setValue(30)
        d_layout.addWidget(val_input)

        btn_box = QHBoxLayout()
        ok_btn = QPushButton("Kaydet")
        ok_btn.setStyleSheet("background-color: #00F0FF; color: #080B10; font-weight: bold;")
        cancel_btn = QPushButton("İptal")

        def on_save():
            name = name_input.text().strip()
            prompt = prompt_input.text().strip()
            if not name:
                return
            t_id = f"custom-{int(time.time())}"
            self.scheduler.schedule_task(
                task_id=t_id,
                name=name,
                prompt=prompt,
                interval_type=type_combo.currentText(),
                interval_value=val_input.value()
            )
            dialog.accept()
            self.refresh_tasks()

        ok_btn.clicked.connect(on_save)
        cancel_btn.clicked.connect(dialog.reject)

        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(ok_btn)
        d_layout.addLayout(btn_box)

        dialog.exec()
