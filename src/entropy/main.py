"""Entropy AI Application Entry Point."""

import argparse
import sys
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
    app.setQuitOnLastWindowClosed(False) # Allows floating/tray background persistence

    # Initialize Core Bridge & Scheduler
    bridge = AgyProcessBridge()
    if args.project:
        bridge.set_project_directory(args.project)

    scheduler = TaskScheduler()
    scheduler.set_execution_callback(lambda task: bridge.send_prompt_async(task.prompt))
    scheduler.start()

    # Launch UI Manager
    ui_manager = EntropyUIManager(bridge=bridge)
    initial_mode = args.mode or config.default_mode
    ui_manager.switch_mode(initial_mode)

    print(f"[{config.app_name}] Started in {initial_mode.upper()} mode.")
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
