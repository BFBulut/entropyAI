# Task Scheduler Specification - Entropy AI

## 1. Overview
The Entropy AI Task Scheduler allows users and sub-agents to define recurring autonomous tasks. Tasks are scheduled to run at regular intervals without requiring manual interaction:
- **Minutely** (`every N minutes`)
- **Hourly** (`every N hours`)
- **Daily** (`at specified time HH:MM`)
- **Weekly** (`on specified day at HH:MM`)

---

## 2. Execution Engine & User Experience
- Implemented using Python's `APScheduler` (BackgroundScheduler) or an asynchronous Qt timer loop running safely off the UI thread.
- **Visual Task Cards (Zen Mode)**:
  - Intuitive interval selectors: *Minutely* (e.g. every 15m), *Hourly* (e.g. every 2h), *Daily* (e.g. at 09:00), *Weekly* (e.g. Monday 10:00).
  - Natural language task input field (e.g., *"Inspect project git diff, run pytest, and log daily summary to Obsidian"*).
  - Visual status chips: `Active`, `Running`, `Last Run: 10 mins ago`, `Next Run: in 5 mins`.
  - One-click trigger ("Run Now") and pause/delete controls.
- Tasks dispatch instructions directly to `AgyProcessBridge` in non-blocking background mode.
- Task definitions and execution logs are persisted locally in `~/.entropy/scheduler/tasks.json` and mirrored to Obsidian daily notes (`DailyNotes/YYYY-MM-DD.md`).

---

## 3. Pre-Configured Autonomous Tasks
1. **Memory Consolidation (Dreaming Cycle)**: Runs every night or during system idle to cluster episodic logs and distill new semantic truths into Obsidian and Supabase.
2. **Project Code Quality Audit**: Daily run inspecting Git changes in the selected project folder, running automated tests, and generating a brief morning report.
3. **MCP Health & Sync Check**: Hourly verification of connected MCP servers and external connections.
