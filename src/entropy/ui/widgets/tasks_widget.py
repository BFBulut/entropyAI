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
from entropy.core.agy_bridge import extract_windows_paths
from entropy.core.task_ledger import task_ledger
from entropy.scheduler.cron_engine import TaskScheduler, ScheduledTask
from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
from entropy.ui.themes.cyber_theme import CYBER_THEME
# Gömülü HTML gövdelerinin renk kaynağı (Faz 12-D.2): düz onaltılık yerine
# `TOKENS`/`TOKENS["viz"]` köprüsü. Bkz. `entropy.ui.design.embedded`.
from entropy.ui.design import TOKENS, icon as design_icon
from entropy.ui.design.embedded import live_palette as _live_palette

# Faz 12-F: canli palet — tema degisince gomulu govdeler de doner.
_P = _live_palette()

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
        title_label = QLabel("Arka plan görevleri")
        title_label.setProperty("role", "heading")
        header.addWidget(title_label)
        header.addStretch()

        # Faz 13: birincil eylem ikonlu ve belirgin (kullanıcı: "düğmeler görünmüyor").
        add_btn = QPushButton("Görev ekle")
        add_btn.setAccessibleName("Görev ekle")
        add_btn.setProperty("variant", "primary")
        add_btn.setIcon(design_icon("add", color=TOKENS["color"]["accent.ink"]))
        add_btn.clicked.connect(self._show_add_dialog)
        header.addWidget(add_btn)

        # Kayıt defteri (tasks_ledger.db) temizliği: bitmiş görev satırlarını siler.
        self.clear_ledger_btn = QPushButton("Kayıt Defteri")
        self.clear_ledger_btn.setAccessibleName("Kayıt Defteri")
        self.clear_ledger_btn.setProperty("variant", "ghost")
        self.clear_ledger_btn.setToolTip("Kayıt defterindeki bitmiş görev kayıtlarını (başarılı/hatalı/iptal) temizle")
        self.clear_ledger_btn.clicked.connect(self._on_clear_ledger)
        header.addWidget(self.clear_ledger_btn)

        refresh_btn = QPushButton("Yenile")
        refresh_btn.setAccessibleName("Yenile")
        refresh_btn.setProperty("variant", "primary")
        refresh_btn.clicked.connect(self.refresh_tasks)
        header.addWidget(refresh_btn)

        self.layout.addLayout(header)

        # Task list
        self.list_widget = QListWidget()
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
        running_ids = self.running_task_ids()

        for t_id, task in self.scheduler.tasks.items():
            item = QListWidgetItem()
            item.setSizeHint(QSize(280, 68))

            row_widget = QWidget()
            row_widget.setMinimumHeight(62)
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

            is_running = t_id in running_ids
            title_color = f"{_P["accent"]}" if task.enabled else f"{_P["text_muted"]}"
            status_badge = f"<span style='color:{_P["ok"]}; font-size:11px; font-weight:bold;'>● AKTİF</span>" if task.enabled else f"<span style='color:{_P["text_muted"]}; font-size:11px;'>○ PASİF</span>"
            if is_running:
                status_badge += f" <span style='color:{_P["warn"]}; font-size:11px; font-weight:bold;'>▶ ÇALIŞIYOR</span>"
            name_lbl = QLabel(f"<b style='color:{title_color}; font-size:13px;'>{task.name}</b> &nbsp; {status_badge}")
            name_lbl.setProperty("role", "label")

            interval_str = f"Periyot: {task.interval_type} ({task.interval_value})"
            next_str = datetime.datetime.fromtimestamp(task.next_run).strftime("%H:%M:%S") if task.next_run else "Planlanmadı"
            status_lbl = QLabel(f"<span style='color:{_P["text_muted"]}; font-size:11px;'>{interval_str} | Sonraki: <span style='color:{_P["ok"]};'>{next_str}</span></span>")
            status_lbl.setProperty("role", "label")

            info_layout.addWidget(name_lbl)
            info_layout.addWidget(status_lbl)
            row_layout.addLayout(info_layout)
            row_layout.addStretch()

            # Run Now button
            run_btn = QPushButton("▶ Çalıştır")
            run_btn.setAccessibleName("▶ Çalıştır")
            run_btn.setProperty("variant", "primary")
            run_btn.clicked.connect(lambda _, t=task: self._run_task_now(t))
            row_layout.addWidget(run_btn)

            # Stop button: yalnızca görev arka planda sürerken etkin
            stop_btn = QPushButton("⏹ Durdur")
            stop_btn.setAccessibleName("⏹ Durdur")
            stop_btn.setObjectName(f"task_stop_{t_id}")
            stop_btn.setToolTip("Süren arka plan görevini iptal et")
            stop_btn.setEnabled(is_running)
            stop_btn.clicked.connect(lambda _, tid=t_id, tname=task.name: self._on_cancel_task(tid, tname))
            row_layout.addWidget(stop_btn)

            # Edit button: ad / periyot / talimat düzenleme
            edit_btn = QPushButton("")
            edit_btn.setIcon(design_icon("edit", color=TOKENS["color"]["text"]))
            edit_btn.setAccessibleName("Zamanlanmış görevi düzenle (ad, periyot, talimat)")
            edit_btn.setObjectName(f"task_edit_{t_id}")
            edit_btn.setProperty("role", "icon")
            edit_btn.setToolTip("Zamanlanmış görevi düzenle (ad, periyot, talimat)")
            edit_btn.clicked.connect(lambda _, t=task: self._show_edit_dialog(t))
            row_layout.addWidget(edit_btn)

            # Delete button
            del_btn = QPushButton("Sil")
            del_btn.setAccessibleName("Sil")
            del_btn.clicked.connect(lambda _, tid=t_id, tname=task.name: self._on_delete_task(tid, tname))
            row_layout.addWidget(del_btn)

            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, row_widget)

    def running_task_ids(self) -> set:
        """Kayıt defterine göre şu anda süren (RUNNING/PENDING) görev kimlikleri."""
        try:
            return {r.get("task_id") for r in task_ledger.get_active_tasks()}
        except Exception:
            return set()

    def _on_cancel_task(self, task_id: str, task_name: str, confirm: bool = True):
        """Süren arka plan görevini iptal eder (tek onay kutusu)."""
        if confirm:
            reply = QMessageBox.question(
                self,
                "Görevi Durdur",
                f"'{task_name}' görevi arka planda sürüyor.\n"
                "Süreç ağacı sonlandırılacak ve kayıt defterine İPTAL yazılacak.\n\nDurdurulsun mu?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        if self.bridge is not None and hasattr(self.bridge, "terminate_background_task"):
            try:
                self.bridge.terminate_background_task(task_id)
            except Exception as e:
                bus.terminal_output_received.emit(f"[Task Scheduler Hata] Görev durdurulamadı: {e}\n")
        try:
            task_ledger.record_task_cancelled(task_id, reason="Kullanıcı görev panelinden durdurdu.", task_name=task_name)
        except Exception:
            pass
        bus.terminal_output_received.emit(f"[Task Scheduler] '{task_name}' görevi kullanıcı tarafından durduruldu.\n")
        bus.task_completed.emit(task_id, False)
        self.refresh_tasks()
        return True

    def _on_delete_task(self, task_id: str, task_name: str, confirm: bool = True):
        """Görevi zamanlayıcıdan ve kayıt defterinden kaldırır (tek onay kutusu)."""
        was_running = task_id in self.running_task_ids()
        if confirm:
            detail = (
                "Görev şu anda çalışıyor; önce süreç durdurulacak.\n" if was_running else ""
            )
            reply = QMessageBox.question(
                self,
                "Görevi Sil",
                f"'{task_name}' görevi kalıcı olarak kaldırılacak.\n"
                f"{detail}Zamanlayıcı kaydı ve kayıt defterindeki (tasks_ledger.db) geçmişi silinecek.\n\nDevam edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return False

        if was_running:
            self._on_cancel_task(task_id, task_name, confirm=False)
        self.scheduler.remove_task(task_id)
        try:
            task_ledger.delete_task(task_id)
        except Exception:
            pass
        bus.terminal_output_received.emit(
            f"[Task Scheduler] '{task_name}' görevi ve kayıt defteri geçmişi silindi.\n"
        )
        self.refresh_tasks()
        return True

    def _on_clear_ledger(self, confirm: bool = True):
        """Kayıt defterindeki bitmiş görev satırlarını temizler (tek onay kutusu)."""
        if confirm:
            reply = QMessageBox.question(
                self,
                "Kayıt Defterini Temizle",
                "Kayıt defterindeki bitmiş (başarılı/hatalı/iptal) görev kayıtları silinecek.\n"
                "Süren görevler etkilenmez.\n\nDevam edilsin mi?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return 0
        try:
            removed = task_ledger.clear_finished()
        except Exception:
            removed = 0
        bus.terminal_output_received.emit(f"[Task Scheduler] Kayıt defterinden {removed} bitmiş görev kaydı silindi.\n")
        self.refresh_tasks()
        return removed

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
                # Faz 11 kapanışı: rüya döngüsü v2 (`memory.dream`). Eski
                # `CognitiveMemorySystem.dream_and_consolidate` 48 saat + epizodik
                # koşuluna bağlıydı; `send_prompt=None` → KOTA HARCAMAZ.
                from entropy.memory.dream import dream_and_consolidate

                report = dream_and_consolidate(memory=cog, send_prompt=None)
                detail = report.summary_line()
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                ovm = ObsidianVaultManager()
                today_str = datetime.date.today().isoformat()
                content = f"# Bilişsel Hafıza Konsolidasyonu & Rüya Raporu ({today_str})\n\n"
                content += f"- Tarih: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                content += f"- Özet: {detail}\n\n## Adım sayaçları\n"
                for _k, _v in report.as_dict().items():
                    content += f"- **{_k}**: {_v}\n"
                rep_path = ovm.save_research_report(f"Konsolide_Hafiza_{today_str}", content, tags=["dream", "consolidation"])
                bus.cognitive_memory_updated.emit()
                bus.knowledge_graph_updated.emit()
                bus.task_notification.emit(task.id, task.name, str(rep_path))
                bus.task_completed.emit(task.id, True)
                bus.terminal_output_received.emit(
                    f"[Task Scheduler] Bilişsel hafıza konsolidasyonu tamamlandı ({detail}; rapor: {rep_path.name}).\n"
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
                task_t = getattr(task, "task_type", "analiz")
                proj_p = getattr(task, "project_path", None)
                if not proj_p:
                    extracted_paths = extract_windows_paths(task.prompt)
                    if extracted_paths:
                        proj_p = str(extracted_paths[0])
                if task_t != "kodlama" and any(k in task.prompt.lower() for k in ["projeyi geliştir", "kodla", "dosya oluştur", "uygula", "geliştir", "build", "develop"]):
                    task_t = "kodlama"
                if proj_p:
                    try:
                        Path(proj_p).resolve().mkdir(parents=True, exist_ok=True)
                    except Exception:
                        pass
                if task_t == "kodlama":
                    exec_prompt = (
                        f"⏰ [OTONOM KODLAMA VE PROJE GELİŞTİRME GÖREVİ: {task.name}]\n"
                        f"Talimat: {task.prompt}\n\n"
                        f"Bu görevi otonom olarak icra et. Bu bir proje/kodlama görevidir! "
                        f"Sadece rapor yazmakla kalma; projenin kodlarını yaz, dosyaları diske oluştur, "
                        f"gerekli araçları (write_to_file, replace_file_content, run_command) ve alt ajanları kullan. "
                        f"Otomatik testleri çalıştır ve doğrula. Sonuçları özetle."
                    )
                else:
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
                    task_name=task.name,
                    project_path=proj_p
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
        # Görev başlarken satırı tazele: "▶ ÇALIŞIYOR" rozeti ve Durdur düğmesi açılır.
        # Sinyal işçi iş parçacığından gelse de alıcı bir QObject slotu olduğu için
        # Qt bunu ana iş parçacığına kuyruklar.
        self.refresh_tasks()

    @Slot(str, bool)
    def _on_task_completed(self, task_id: str, success: bool):
        self.refresh_tasks()

    def _show_add_dialog(self):
        """Yeni zamanlanmış görev ekleme kutusu."""
        return self._show_task_dialog(None)

    def _show_edit_dialog(self, task: ScheduledTask):
        """Var olan zamanlanmış görevi düzenleme kutusu."""
        return self._show_task_dialog(task)

    def apply_task_edit(
        self,
        task: ScheduledTask,
        name: str,
        prompt: str,
        interval_type: str,
        interval_value: int,
        task_type: str = "analiz",
        project_path: Optional[str] = None,
    ) -> ScheduledTask:
        """Görev alanlarını günceller, sonraki çalışma zamanını tazeler ve kaydeder."""
        task.name = name or task.name
        task.prompt = prompt
        task.interval_type = interval_type
        task.interval_value = interval_value
        task.task_type = task_type
        task.project_path = project_path
        if task.enabled:
            task.next_run = self.scheduler.compute_next_run(
                task.interval_type, task.interval_value, task.day_of_week, from_time=time.time()
            )
        self.scheduler._save_tasks()
        bus.terminal_output_received.emit(f"[Task Scheduler] '{task.name}' görevi güncellendi.\n")
        self.refresh_tasks()
        return task

    def _show_task_dialog(self, task: Optional[ScheduledTask] = None):
        """Görev ekleme/düzenleme kutusu; task verilirse alanlar dolu gelir."""
        is_edit = task is not None
        dialog = QDialog(self)
        dialog.setWindowTitle("Otonom Görevi Düzenle" if is_edit else "Yeni Otonom Görev Ekle")
        dialog.setFixedWidth(400)

        d_layout = QVBoxLayout(dialog)

        d_layout.addWidget(QLabel("Görev Adı:"))
        name_input = QLineEdit()
        name_input.setPlaceholderText("örn: Proje Geliştirme veya Git Durumu Raporu")
        d_layout.addWidget(name_input)

        d_layout.addWidget(QLabel("Görev Türü:"))
        task_type_combo = QComboBox()
        task_type_combo.addItems(["analiz", "kodlama"])
        d_layout.addWidget(task_type_combo)

        d_layout.addWidget(QLabel("Hedef Proje Dizini (Opsiyonel):"))
        proj_input = QLineEdit()
        proj_input.setPlaceholderText("örn: C:\\Entropy Agent Desk")
        d_layout.addWidget(proj_input)

        d_layout.addWidget(QLabel("Talimat / Prompt:"))
        prompt_input = QLineEdit()
        prompt_input.setPlaceholderText("örn: Projeyi geliştir, mimariyi kur ve testleri yaz")
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

        # Düzenleme kipinde mevcut değerlerle doldur
        if is_edit:
            name_input.setText(task.name)
            prompt_input.setText(task.prompt or "")
            proj_input.setText(getattr(task, "project_path", None) or "")
            t_idx = task_type_combo.findText(getattr(task, "task_type", "analiz"))
            if t_idx >= 0:
                task_type_combo.setCurrentIndex(t_idx)
            i_idx = type_combo.findText(task.interval_type)
            if i_idx >= 0:
                type_combo.setCurrentIndex(i_idx)
            else:
                type_combo.addItem(task.interval_type)
                type_combo.setCurrentText(task.interval_type)
            val_input.setRange(0, 1440)
            val_input.setValue(int(task.interval_value or 0))

        btn_box = QHBoxLayout()
        ok_btn = QPushButton("Kaydet")
        ok_btn.setAccessibleName("Kaydet")
        ok_btn.setProperty("variant", "primary")
        cancel_btn = QPushButton("İptal")
        cancel_btn.setAccessibleName("İptal")

        def on_save():
            name = name_input.text().strip()
            prompt = prompt_input.text().strip()
            if not name:
                return
            t_id = f"custom-{int(time.time())}"
            proj_val = proj_input.text().strip() or None
            selected_type = task_type_combo.currentText()
            if not proj_val and prompt:
                extracted = extract_windows_paths(prompt)
                if extracted:
                    proj_val = str(extracted[0])
            if selected_type == "analiz" and any(k in prompt.lower() for k in ["projeyi geliştir", "kodla", "dosya oluştur", "uygula", "geliştir", "build", "develop"]):
                selected_type = "kodlama"
            if is_edit:
                self.apply_task_edit(
                    task,
                    name=name,
                    prompt=prompt,
                    interval_type=type_combo.currentText(),
                    interval_value=val_input.value(),
                    task_type=selected_type,
                    project_path=proj_val,
                )
                dialog.accept()
                return
            self.scheduler.schedule_task(
                task_id=t_id,
                name=name,
                prompt=prompt,
                interval_type=type_combo.currentText(),
                interval_value=val_input.value(),
                task_type=selected_type,
                project_path=proj_val
            )
            dialog.accept()
            self.refresh_tasks()

        ok_btn.clicked.connect(on_save)
        cancel_btn.clicked.connect(dialog.reject)

        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(ok_btn)
        d_layout.addLayout(btn_box)

        dialog.exec()

    def closeEvent(self, event):
        if self.scheduler:
            try:
                self.scheduler.stop()
            except Exception:
                pass
        super().closeEvent(event)

