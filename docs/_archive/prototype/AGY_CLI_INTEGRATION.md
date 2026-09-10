# Antigravity (AGY) CLI Integration Specification

## 1. Authentication & Zero-API Philosophy
- Entropy AI connects strictly via the installed and authenticated `agy` CLI (`C:\Program Files\...` or system PATH).
- No external LLM API keys (OpenAI, Anthropic, Gemini API keys) are required or prompted from the user.
- Authentication status is confirmed via `agy` session handshake.

---

## 2. Process Execution & Real-Time Output Piping

In adherence to `RULE[agent-ui-routing.md]`:
- Process runs via `QProcess` or asynchronous `subprocess.Popen`.
- Output is read chunk-by-chunk without blocking the main event loop.
- Standard Output and Standard Error are parsed in real-time:
  - Regex detection of model names -> emits `sig_model_name_updated(model_str)`.
  - Token markers and response text -> emits `sig_chunk_received(text_str)`.
  - Tool execution logs -> routed to the Terminal Panel.

```python
# Streaming Execution Pattern
class AgyProcessBridge(QObject):
    sig_chunk = Signal(str)
    sig_model_detected = Signal(str)
    sig_finished = Signal(int)

    def run_prompt(self, prompt: str, project_dir: str, mode: str = "accept-edits"):
        cmd = [
            "agy",
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--mode", mode,
            "--add-dir", project_dir
        ]
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self._on_stdout)
        self.process.start(cmd[0], cmd[1:])
```

---

## 3. Dynamic Model Identification Rule Compliance

In adherence to `RULE[agent-ui-models.md]`:
1. Model names are **never** hardcoded.
2. The UI initializes with `[Model: Unknown]`.
3. As soon as `agy` returns its session headers or output metadata, the regex parser extracts the active model (e.g. "gemini-2.5-pro", "claude-3-7-sonnet") and updates the badge dynamically.

---

## 4. MCP Management Integration

Entropy AI provides a graphical toggle dock for Model Context Protocol servers:
- Query installed MCPs: `agy mcp list`
- Enable an MCP: `agy mcp enable <server_name>`
- Disable an MCP: `agy mcp disable <server_name>`
- Add a new custom MCP: `agy mcp add <name> <type> <command/url>`
