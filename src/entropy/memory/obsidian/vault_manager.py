"""Obsidian Vault integration for Entropy AI exocortex & memory graph."""

import datetime
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from entropy.core.config import config

class ObsidianVaultManager:
    """Manages the local Obsidian markdown vault as Entropy AI's persistent memory."""

    WIKILINK_PATTERN = re.compile(r"\[\[(.*?)\]\]")

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = Path(vault_path or config.obsidian_vault_path)
        self.entropy_dir = self.vault_path / "Entropy"
        self.daily_notes_dir = self.entropy_dir / "DailyNotes"
        self.reports_dir = self.entropy_dir / "Reports"
        self.projects_dir = self.entropy_dir / "Projects"
        self.memory_file = self.entropy_dir / "MEMORY.md"

        self._ensure_directories()

    def _ensure_directories(self):
        """Create necessary vault directories if they don't exist."""
        for d in [self.entropy_dir, self.daily_notes_dir, self.reports_dir, self.projects_dir]:
            d.mkdir(parents=True, exist_ok=True)

        if not self.memory_file.exists():
            self.memory_file.write_text(
                "# Entropy AI - Global Memory & Architecture Decisions\n\n"
                "## System Beliefs & Core Directives\n"
                "- System Name: Entropy AI\n"
                "- Core Framework: Antigravity CLI (agy)\n"
                "- Privacy Policy: Local data-on-disk priority\n\n"
                "## Learned User Preferences\n"
                "- Zero external LLM API keys requested\n"
                "- Multi-modal interaction with Ctrl+C / Ctrl+V\n",
                encoding="utf-8"
            )

    def read_global_memory(self) -> str:
        """Read the root MEMORY.md file."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def append_to_global_memory(self, category: str, note: str):
        """Append an insight or decision to MEMORY.md."""
        current = self.read_global_memory()
        header = f"\n### {category} ({datetime.date.today().isoformat()})\n- {note}\n"
        self.memory_file.write_text(current + header, encoding="utf-8")

    def append_daily_log(self, entry: str) -> Path:
        """Write an episodic log entry to today's daily note in the Obsidian vault."""
        today = datetime.date.today().strftime("%Y-%m-%d")
        daily_file = self.daily_notes_dir / f"{today}.md"
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")

        header = f"# Entropy AI Session Log - {today}\n\n" if not daily_file.exists() else ""
        formatted = f"{header}[{timestamp}] {entry}\n"

        with open(daily_file, "a", encoding="utf-8") as f:
            f.write(formatted)
        return daily_file

    def save_research_report(self, title: str, content: str, tags: Optional[List[str]] = None) -> Path:
        """Save a research dossier in the Reports directory with wikilinks and frontmatter."""
        safe_title = "".join([c if c.isalnum() or c in " -_" else "_" for c in title]).strip()
        report_file = self.reports_dir / f"{safe_title}.md"
        
        tag_str = ", ".join(tags or ["entropy-ai", "research-report"])
        frontmatter = (
            f"---\n"
            f"title: \"{title}\"\n"
            f"date: {datetime.date.today().isoformat()}\n"
            f"tags: [{tag_str}]\n"
            f"agent: Entropy AI\n"
            f"---\n\n"
        )
        report_file.write_text(frontmatter + content, encoding="utf-8")
        return report_file

    def list_reports(self) -> List[Dict[str, str]]:
        """List all research reports available in the vault."""
        reports = []
        for file in sorted(self.reports_dir.glob("*.md"), reverse=True):
            reports.append({
                "title": file.stem.replace("_", " "),
                "path": str(file),
                "modified": datetime.datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            })
        return reports

    def build_knowledge_graph(self) -> Dict[str, List[Dict[str, str]]]:
        """Parse all markdown files in the Entropy folder and extract nodes & links."""
        nodes = []
        links = []
        node_ids: Set[str] = set()

        for file in self.entropy_dir.rglob("*.md"):
            name = file.stem
            category = file.parent.name
            node_id = f"{category}/{name}"

            if node_id not in node_ids:
                node_ids.add(node_id)
                nodes.append({
                    "id": node_id,
                    "name": name,
                    "group": category,
                    "path": str(file)
                })

            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
                matches = self.WIKILINK_PATTERN.findall(content)
                for target in matches:
                    links.append({
                        "source": node_id,
                        "target": target.strip()
                    })
            except Exception:
                continue

        return {"nodes": nodes, "links": links}
