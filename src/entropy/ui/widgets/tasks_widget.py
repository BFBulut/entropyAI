"""Task Scheduler Management Widget for Zen Mode."""

import time
import datetime
import threading
from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt, Slot, QSize
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

    def __init__(self, parent=None, scheduler: Optional[TaskScheduler] = None, bridge=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        self.scheduler = scheduler or TaskScheduler.get_instance()
        self.bridge = bridge or getattr(parent, "bridge", None)

        # Ensure background scheduler loop is running
        self.scheduler.start()

        # Set execution callback for scheduled background triggers
        self.scheduler.set_execution_callback(self._run_task_now)

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
        """Populate the task list with modern custom cybernetic row widgets."""
        self.list_widget.clear()

        for t_id, task in self.scheduler.tasks.items():
            item = QListWidgetItem()
            item.setSizeHint(QSize(280, 68))

            row_widget = QWidget()
            row_widget.setMinimumHeight(62)
            row_widget.setStyleSheet("""
                QWidget {
                    background-color: #0E1420;
                    border: 1px solid #1F2B42;
                    border-radius: 6px;
                }
                QWidget:hover {
                    border-color: #00F0FF;
                }
            """)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(10, 6, 10, 6)
            row_layout.setSpacing(10)

            # Enable checkbox
            cb = QCheckBox()
            cb.setChecked(task.enabled)
            cb.setToolTip("Görevi etkinleştir / devre dışı bırak")
            cb.toggled.connect(lambda checked, t=task: self._on_toggle_task(t, checked))
            row_layout.addWidget(cb)

            # Details
            info_layout = QVBoxLayout()
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(2)

            title_color = "#00F0FF" if task.enabled else "#8B949E"
            status_badge = "<span style='color:#00FF9D; font-size:10px; font-weight:bold;'>● AKTİF</span>" if task.enabled else "<span style='color:#8B949E; font-size:10px;'>○ PASİF</span>"
            name_lbl = QLabel(f"<b style='color:{title_color}; font-size:12px;'>{task.name}</b> &nbsp; {status_badge}")
            name_lbl.setStyleSheet("background: transparent; border: none;")

            interval_str = f"Periyot: {task.interval_type} ({task.interval_value})"
            next_str = datetime.datetime.fromtimestamp(task.next_run).strftime("%H:%M:%S") if task.next_run else "Planlanmadı"
            status_lbl = QLabel(f"<span style='color:#8B949E; font-size:11px;'>{interval_str} | Sonraki: <span style='color:#00FF9D;'>{next_str}</span></span>")
            status_lbl.setStyleSheet("background: transparent; border: none;")

            info_layout.addWidget(name_lbl)
            info_layout.addWidget(status_lbl)
            row_layout.addLayout(info_layout)
            row_layout.addStretch()

            # Run Now button
            run_btn = QPushButton("▶ Çalıştır")
            run_btn.setFixedHeight(26)
            run_btn.setStyleSheet("""
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
            run_btn.clicked.connect(lambda _, t=task: self._run_task_now(t))
            row_layout.addWidget(run_btn)

            # Delete button
            del_btn = QPushButton("🗑️ Sil")
            del_btn.setFixedHeight(26)
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #24141A;
                    color: #FF4D4D;
                    border: 1px solid #FF4D4D;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #FF4D4D;
                    color: #080B10;
                }
            """)
            del_btn.clicked.connect(lambda _, tid=t_id, tname=task.name: self._on_delete_task(tid, tname))
            row_layout.addWidget(del_btn)

            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row_widget)

    def _on_delete_task(self, task_id: str, task_name: str):
        reply = QMessageBox.question(
            self,
            "Görevi Sil",
            f"'{task_name}' görevini listeden kaldırmak istediğinizden emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.scheduler.remove_task(task_id)
            bus.terminal_output_received.emit(f"[Task Scheduler] '{task_name}' görevi başarıyla silindi.\n")
            self.refresh_tasks()

    def _on_toggle_task(self, task: ScheduledTask, enabled: bool):
        task.enabled = enabled
        now = time.time()
        if enabled:
            task.next_run = self.scheduler.compute_next_run(
                task.interval_type, task.interval_value, task.day_of_week, from_time=now
            )
            bus.terminal_output_received.emit(
                f"[Task Scheduler] '{task.name}' görevi AKTİFLEŞTİRİLDİ (Otomatik periyotta çalışacak).\n"
            )
        else:
            task.next_run = None
            bus.terminal_output_received.emit(
                f"[Task Scheduler] '{task.name}' görevi DEVRE DIŞI (PASİF) bırakıldı.\n"
            )
        self.scheduler._save_tasks()
        self.refresh_tasks()

    def _run_task_now(self, task: ScheduledTask):
        """Execute a task in the background without blocking the UI thread or locking interactive chat."""
        thread = threading.Thread(target=self._execute_task_logic, args=(task,), daemon=True)
        thread.start()

    def _execute_task_logic(self, task: ScheduledTask):
        bus.terminal_output_received.emit(f"\n[Task Scheduler] '{task.name}' görevi anlık olarak çalıştırılıyor...\n")
        
        if task.id == "daily-dreaming":
            try:
                cog = CognitiveMemorySystem()
                rules = cog.dream_and_consolidate()
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                ovm = ObsidianVaultManager()
                today_str = datetime.date.today().isoformat()
                content = f"# Bilişsel Hafıza Konsolidasyonu & Rüya Raporu ({today_str})\n\n"
                content += f"- Sentezlenen Kural Sayısı: {len(rules)}\n- Tarih: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n## Konsolide Edilen Kurallar:\n"
                for r in rules:
                    content += f"- {r}\n"
                rep_path = ovm.save_research_report(f"Konsolide_Hafiza_{today_str}", content, tags=["dream", "consolidation"])
                bus.report_created.emit(str(rep_path))
                bus.cognitive_memory_updated.emit()
                bus.knowledge_graph_updated.emit()
                bus.task_notification.emit(task.id, task.name, str(rep_path))
                bus.task_completed.emit(task.id, True)
                bus.terminal_output_received.emit(
                    f"[Task Scheduler] Bilişsel hafıza konsolidasyonu tamamlandı ({len(rules)} semantik kural sentezlendi, rapor: {rep_path.name}).\n"
                )
            except Exception as e:
                bus.terminal_output_received.emit(f"[Task Scheduler Hata] Konsolidasyon hatası: {e}\n")
                bus.task_completed.emit(task.id, False)

        elif task.id == "obsidian-sync":
            try:
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                ovm = ObsidianVaultManager()
                log_path = ovm.append_daily_log("Periyodik arka plan bellek senkronu gerçekleştirildi.")
                notes_count = len(ovm.list_all_notes())
                content = f"# Obsidian Exocortex Senkronizasyon Raporu\n\n- Taranan Not Sayısı: {notes_count}\n- Günlük Kayıt: {log_path.name}\n- Senkron Zamanı: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                rep_path = ovm.save_research_report("Obsidian_Senkronizasyon_Raporu", content, tags=["sync", "obsidian"])
                bus.report_created.emit(str(rep_path))
                bus.cognitive_memory_updated.emit()
                bus.knowledge_graph_updated.emit()
                bus.task_notification.emit(task.id, task.name, str(rep_path))
                bus.task_completed.emit(task.id, True)
                bus.terminal_output_received.emit(
                    f"[Task Scheduler] Obsidian senkronizasyonu tamamlandı ({notes_count} not tarandı, günlük kaydedildi: {log_path.name}).\n"
                )
            except Exception as e:
                bus.terminal_output_received.emit(f"[Task Scheduler Hata] Obsidian senkron hatası: {e}\n")
                bus.task_completed.emit(task.id, False)

        elif task.id == "rag-reindex":
            try:
                from entropy.memory.rag.project_indexer import ProjectIndexer
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                from entropy.core.config import config
                indexer = ProjectIndexer(root_dir=config.default_project_path)
                indexed_count = indexer.scan_and_index()
                ovm = ObsidianVaultManager()
                content = f"# Kod Tabanı RAG İndeksleme Raporu\n\n- İndekslenen Kod Dosyası: {indexed_count}\n- Proje Dizini: {config.default_project_path}\n- Zaman: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                rep_path = ovm.save_research_report("Kod_Tabani_RAG_Raporu", content, tags=["rag", "codebase"])
                bus.report_created.emit(str(rep_path))
                bus.cognitive_memory_updated.emit()
                bus.knowledge_graph_updated.emit()
                bus.task_notification.emit(task.id, task.name, str(rep_path))
                bus.task_completed.emit(task.id, True)
                bus.terminal_output_received.emit(
                    f"[Task Scheduler] Kod tabanı indeksleme (RAG) tamamlandı ({indexed_count} dosya indekslendi, rapor: {rep_path.name}).\n"
                )
            except Exception as e:
                bus.terminal_output_received.emit(f"[Task Scheduler Hata] RAG indeksleme hatası: {e}\n")
                bus.task_completed.emit(task.id, False)

        elif task.prompt:
            bus.terminal_output_received.emit(f"[Task Scheduler] '{task.name}' görevi AGY motoruna gönderiliyor: {task.prompt}\n")
            if self.bridge:
                exec_prompt = (
                    f"⏰ [OTONOM PLANLI GÖREV: {task.name}]\n"
                    f"Talimat: {task.prompt}\n\n"
                    f"Bu görevi otonom olarak icra et. Gerekli araç ve yeteneklerini kullan. Elde ettiğin bulguları ve analizleri "
                    f"ayrıntılı bir araştırma raporu olarak yapılandır, Obsidian Reports/ altına kaydet ve bilişsel hafıza sistemine işle."
                )
                self.bridge.send_prompt_async(
                    prompt=exec_prompt,
                    is_background=True,
                    task_id=task.id,
                    task_name=task.name
                )
            else:
                bus.terminal_output_received.emit("[Task Scheduler Uyarı] AGY Bridge bağlı değil, görev gönderilemedi.\n")
                bus.task_completed.emit(task.id, False)

        bus.task_triggered.emit(task.id, task.name)
        task.last_run = time.time()
        task.next_run = self.scheduler.compute_next_run(
            task.interval_type, task.interval_value, task.day_of_week, from_time=time.time()
        )
        self.scheduler._save_tasks()

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
