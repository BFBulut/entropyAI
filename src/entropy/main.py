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

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(config.app_name)
    app.setQuitOnLastWindowClosed(False)

    icon_path = Path.cwd() / "entropy.ico"
    if not icon_path.exists():
        icon_path = Path(__file__).resolve().parents[2] / "entropy.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Initialize Core Bridge & Scheduler
    bridge = AgyProcessBridge()
    if args.project:
        bridge.set_project_directory(args.project)

    scheduler = TaskScheduler()

    def handle_scheduled_task(task):
        from entropy.core.event_bus import bus
        if task.id == "daily-dreaming":
            try:
                from entropy.memory.supabase.cognitive_memory import CognitiveMemorySystem
                cog = CognitiveMemorySystem()
                rules = cog.dream_and_consolidate()
                bus.terminal_output_received.emit(f"[Otonom Görev] Hafıza konsolidasyonu tamamlandı ({len(rules)} kural sentezlendi).\n")
            except Exception as e:
                bus.terminal_output_received.emit(f"[Otonom Görev Hata] {e}\n")
        elif task.id == "obsidian-sync":
            try:
                from entropy.memory.obsidian.vault_manager import ObsidianVaultManager
                ovm = ObsidianVaultManager()
                log_p = ovm.append_daily_log("Otonom arka plan senkronu.")
                bus.terminal_output_received.emit(f"[Otonom Görev] Obsidian günlüğü senkronlandı: {log_p.name}\n")
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

    print(f"[{config.app_name}] Started in {initial_mode.upper()} mode.")
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
