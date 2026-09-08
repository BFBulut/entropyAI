"""Entropy AI Application Entry Point."""

import argparse
import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from entropy.core.config import config
from entropy.core.agy_bridge import AgyProcessBridge
from entropy.scheduler.cron_engine import TaskScheduler
from entropy.ui.manager import EntropyUIManager

def main():
    parser = argparse.ArgumentParser(description="Entropy AI Agentic Desktop Operating System")
    parser.add_argument("--mode", choices=["zen", "floating", "chat"], default=None, help="Initial desktop mode")
    parser.add_argument("--project", default=None, help="Project directory to mount")
    args = parser.parse_args()

    # Pencereli derlemede stderr yok: kapanış nedenleri ancak dosyaya yazılırsa görülür.
    from entropy.core.config import STATE_DIR
    from entropy.core.crash_log import install_crash_logging
    install_crash_logging(STATE_DIR / "logs")

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setQuitOnLastWindowClosed(False)

    # Tek kopya: zaten çalışan bir kopya varsa onu öne getirip çık. Pencere
    # kapatılınca süreç tepside yaşadığı için ikinci başlatmalar aynı belleği
    # paylaşan kopyalar üretiyor ve donmaya yol açıyordu.
    from entropy.core.single_instance import SingleInstanceGuard
    guard = SingleInstanceGuard(parent=app)
    if not guard.try_acquire():
        guard.notify_existing()
        print(f"[{config.app_name}] Zaten çalışıyor; mevcut pencere öne getirildi.")
        return 0

    icon_path = Path.cwd() / "entropy.ico"
    if not icon_path.exists():
        icon_path = Path(__file__).resolve().parents[2] / "entropy.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Initialize Core Bridge & Scheduler
    bridge = AgyProcessBridge()
    if args.project:
        bridge.set_project_directory(args.project)

    # Önceki oturum bir arka plan görevi sürerken kapandıysa ledger'da o satır
    # sonsuza dek RUNNING kalıyordu; görev panelinde hayalet iş olarak görünüyordu.
    from entropy.core.task_ledger import task_ledger
    orphaned = task_ledger.mark_orphans_failed()
    if orphaned:
        print(f"[{config.app_name}] Önceki oturumdan yarım kalan {orphaned} görev kapatıldı.")

    scheduler = TaskScheduler.get_instance()

    def handle_scheduled_task(task):
        from entropy.core.event_bus import bus
        if task.id == "daily-dreaming":
            try:
                from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
                cog = CognitiveMemorySystem()
                rules = cog.dream_and_consolidate()
                bus.terminal_output_received.emit(f"[Otonom Görev] Hafıza konsolidasyonu tamamlandı ({len(rules)} özet).\n")

                # Gerçek sentez AGY ile, arka planda: ledger'a kaydolur, sohbeti kilitlemez.
                # Çıktı rapor arşivine değil doğrudan bilişsel belleğe yazılır.
                consolidation_prompt = cog.build_consolidation_prompt()
                if consolidation_prompt:
                    def _store(full_text: str, ok: bool, _cog=cog):
                        if ok and _cog.store_consolidation(full_text):
                            bus.terminal_output_received.emit("[Otonom Görev] AGY konsolidasyonu belleğe işlendi.\n")
                            bus.cognitive_memory_updated.emit()

                    bridge.send_background_task_async(
                        task_id=f"consolidate-{int(__import__('time').time())}",
                        task_name="Bilişsel Konsolidasyon",
                        prompt=consolidation_prompt,
                        mode="accept-edits",  # "plan" modu keşif/plan döngüsü tetikliyor (bkz. distiller)
                        on_result=_store,
                        save_report=False,
                    )
            except Exception as e:
                bus.terminal_output_received.emit(f"[Otonom Görev Hata] {e}\n")
        elif task.id == "obsidian-sync":
            try:
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                ovm = ObsidianVaultManager()
                log_p = ovm.append_daily_log("Otonom arka plan senkronu.")
                moc_p = ovm.sync_map_of_content()
                bus.terminal_output_received.emit(f"[Otonom Görev] Obsidian günlüğü ve {moc_p.name} senkronlandı.\n")
            except Exception as e:
                bus.terminal_output_received.emit(f"[Otonom Görev Hata] {e}\n")
        elif task.id == "rag-reindex":
            try:
                from entropy.memory.rag.project_indexer import ProjectIndexer
                indexer = ProjectIndexer(config.default_project_path)
                cnt = indexer.scan_and_index()
                bus.terminal_output_received.emit(f"[Otonom Görev] Proje kodları indekslendi ({cnt} dosya).\n")
            except Exception as e:
                bus.terminal_output_received.emit(f"[Otonom Görev Hata] {e}\n")
        elif task.prompt:
            bridge.send_prompt_async(task.prompt)

    scheduler.set_execution_callback(handle_scheduled_task)
    scheduler.start()

    # Launch UI Manager
    ui_manager = EntropyUIManager(bridge=bridge)
    initial_mode = args.mode or config.default_mode
    ui_manager.switch_mode(initial_mode)
    guard.activated.connect(ui_manager.bring_to_front)

    print(f"[{config.app_name}] Started in {initial_mode.upper()} mode.")
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
