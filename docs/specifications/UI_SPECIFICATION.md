# UI Specification - Entropy AI Tri-Modal Interface

## 1. Design Aesthetic & Themes
- **Visual Identity**: High-contrast, sleek cybernetic workstation. Deep dark backgrounds (`#0B0F19`), neon cyan accents (`#00F0FF`), amber alert highlights (`#FFB300`), and clean monospace typography for code/terminals.
- **Window Flags**: Frameless (`Qt.WindowType.FramelessWindowHint`), customizable transparency, and borderless window management.

---

## 2. Mode 1: Zen Mode (Borderless Fullscreen Workstation)

```text
+-----------------------------------------------------------------------------------+
|  [ENTROPY AI]  [Project: MyEngine]  [Model: Dynamic]  [Tokens: 4,120]  [Minimize/X] |
+----------------------+-----------------------------+------------------------------+
|                      |                             |                              |
|   RESEARCH & REPORTS |     CENTRAL AI CORE         |       INTERACTIVE            |
|   EXPLORER           |   (Glowing/Pulsing Orb)     |       KNOWLEDGE GRAPH        |
|                      |                             |     (Obsidian / GraphRAG)    |
|   - Daily Reports    |   Status: Thinking / Idle   |                              |
|   - Task Analysis    |   Active Tool: Pydantic AI  |   [Node: Auth] <-> [Node: DB]|
|   - Memory Audits    |                             |                              |
|                      |                             |                              |
+----------------------+-----------------------------+------------------------------+
|                      |                                                            |
|   MCP TOOL STATUS    |   SPLIT REAL-TIME TERMINAL & CHAT CONSOLE                  |
|   - StitchMCP (ON)   |   entropy@core:~$ agy --mode plan                          |
|   - Obsidian  (ON)   |   [Real-time stdout stream with streaming buffer]          |
|   - Supabase  (ON)   |                                                            |
+----------------------+------------------------------------------------------------+
```

### Key Capabilities:
- **Central AI Core Visualizer**: Custom widget rendering an interactive particle/energy sphere. Glow intensity and pulse speed dynamically synchronize with stdout chunk ingestion.
- **Live Project Manager & Git Tree**: Header dropdown and sidebar file tree allowing instant switching/drag-and-drop of project folders, seamlessly feeding `--add-dir <path>` into the underlying `agy` CLI session and monitoring git diff status.
- **Research Reports Viewer**: Markdown and HTML renderer with table-of-contents navigation and generative UI artifact embedding.
- **Knowledge Graph Viewer**: Powered by `QWebEngineView` with interactive D3/Cytoscape force-directed network graphs, visualizing Obsidian bidirectional `[[Wikilinks]]`, Supabase episodic memories, and node-detail inspection drawers.
- **Infinite Split Terminal**: Pane splitting (horizontal/vertical) for parallel agent execution.
- **Active MCP Drawer**: Toggle buttons to enable/disable servers via `agy mcp enable <name>` / `agy mcp disable <name>`.

---

## 3. Mode 2: Floating Mode (Minimalist Ambient Core)

```text
       +---------------+
       |   ((  *  ))   |   <-- Draggable glowing orb widget (e.g. 120x120 px)
       +---------------+
```

### Key Capabilities:
- **Draggable & Translucent**: Always-on-top frameless floating widget that can be placed anywhere on multi-monitor setups.
- **State Reflection**: Ambient breathing glow when idle; rapid pulsing ripple during agent compute; amber flicker on warning.
- **Interaction Mechanics**:
  - **Global Hotkey**: `Win + Alt + E` instantly toggles between Zen Mode and Floating/Minimized state.
  - **Double-Click**: Instantly summons/dismisses the floating Chat Mode window.
  - **System Tray**: Windows taskbar notification area icon with quick access to all modes and status.
- **Right-Click Context Menu**:
  - `📌 Pin On Top` (Toggle `WindowStaysOnTopHint`)
  - `🧘 Enter Zen Mode` (Transitions smoothly into full workstation)
  - `💬 Open Chat Mode`
  - `⚡ Quick Task Prompt`
  - `❌ Quit`

---

## 4. Mode 3: Chat Mode (Floating Conversational Workspace)

```text
+-------------------------------------------------------------+
|  Entropy AI Chat   [Model: Claude 3.7 / Gemini 2.5]   [_][X] |
+-------------------------------------------------------------+
|  Assistant: Codebase indexed. Found 42 source files.        |
|  User: [Pasted Image: diagram.png]                          |
|  Assistant: I see the architecture diagram. Proceeding...   |
|                                                             |
+-------------------------------------------------------------+
|  [>_ Collapsible Real-Time Terminal Output Drawer]          |
+-------------------------------------------------------------+
|  [ Type prompt...                             ] [📎] [Send] |
+-------------------------------------------------------------+
```

### Key Capabilities:
- **Multi-Modal Clipboard**: Intercepts `Ctrl+V` key and clipboard paste events. When `QClipboard.mimeData().hasImage()` is detected:
  - The image is saved as a crisp PNG to `.entropy/staging/images/<timestamp_hash>.png`.
  - A compact visual thumbnail pill with a remove `[x]` button appears right above the chat input field.
  - The local image path is passed cleanly to the `agy` CLI multimodal context, preventing token explosion.
- **Collapsible Terminal Drawer**: Slides up from bottom to inspect raw subprocess CLI execution without obstructing chat history.
- **Sliding Context Window Display**: Shows real-time message count and auto-summarization indicators.
